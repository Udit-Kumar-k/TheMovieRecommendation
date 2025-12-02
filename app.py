from flask import Flask, request, jsonify
from sklearn.metrics.pairwise import linear_kernel
from data_loader import get_data, get_basic_data
from flask import Flask, render_template
import pandas as pd

app = Flask(__name__)

USE_RECOMMENDATION = True # 🔁 Set to True only if you have FAISS files

if USE_RECOMMENDATION:
    df, title_to_index, index = get_data()
    # ⚡️ Pre-compute list of titles once at startup for performance
    ALL_TITLES = list(title_to_index.keys())
    
    # Create a map of title -> popularity for sorting
    # Handle cases where popularity might be missing or NaN
    TITLE_TO_POPULARITY = {}
    for title, idx in title_to_index.items():
        pop = df.iloc[idx].get('popularity', 0)
        TITLE_TO_POPULARITY[title] = float(pop) if pd.notna(pop) else 0.0
        
else:
    df = get_basic_data()
    ALL_TITLES = []
    TITLE_TO_POPULARITY = {}


@app.route('/')
def home():
    return render_template('index.html')


from rapidfuzz import process, fuzz
from functools import lru_cache

@lru_cache(maxsize=1024)
def get_suggestions(query):
    # Helper to get popularity (default to 0)
    def get_pop(t):
        return TITLE_TO_POPULARITY.get(t, 0)

    # 1. Exact Prefix Match (Highest Priority)
    # Sort by popularity (descending) to show most popular first
    starts_with = sorted(
        [t for t in ALL_TITLES if t.startswith(query)], 
        key=get_pop, 
        reverse=True
    )
    
    # 2. Word Boundary Match (High Priority)
    query_with_space = " " + query
    word_boundary = sorted(
        [t for t in ALL_TITLES if query_with_space in t and t not in starts_with], 
        key=get_pop,
        reverse=True
    )
    
    # Combine fast matches
    results = (starts_with + word_boundary)[:10]
    
    # 3. Fuzzy Match (Fallback)
    if len(results) < 10:
        remaining_limit = 10 - len(results)
        fuzzy_results = process.extract(
            query, 
            ALL_TITLES, 
            scorer=fuzz.WRatio, 
            limit=remaining_limit, 
            score_cutoff=80
        )
        
        existing_set = set(results)
        # Sort fuzzy results by popularity too, just in case
        fuzzy_matches = []
        for match in fuzzy_results:
            if match[0] not in existing_set:
                fuzzy_matches.append(match[0])
        
        # Sort the fuzzy matches by popularity
        fuzzy_matches.sort(key=get_pop, reverse=True)
        results.extend(fuzzy_matches)
                
    # Enrich with poster paths
    final_results = []
    for title in results[:10]:
        idx = title_to_index.get(title)
        poster_path = ""
        if idx is not None:
            poster = df.iloc[idx].get('poster_path', '')
            poster_path = poster if pd.notna(poster) else ""
            
        final_results.append({
            'title': title,
            'poster_path': poster_path
        })
                
    return final_results

@app.route('/suggest', methods=['GET'])
def suggest():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])
    
    results = get_suggestions(query)
    return jsonify(results)

@app.route('/smart_recommend', methods=['GET'])
def smart_recommend():
    try:
        title = request.args.get('title', '').strip().lower()
        genre = request.args.get('genre', '').strip().lower()
        num_results = int(request.args.get('limit', 30))  # Default to 30

        print(f"[INFO] Searching for title: {title} | genre: {genre}")

        if not title:
            return jsonify({"error": "Missing 'title' parameter."}), 400

        if title not in title_to_index:
            # Try to find a close match
            choices = list(title_to_index.keys())
            best_match = process.extractOne(title, choices)
            
            if best_match and best_match[1] > 70: # 70% confidence threshold
                print(f"[INFO] Exact match not found. Using best match: {best_match[0]} (Score: {best_match[1]})")
                title = best_match[0]
            else:
                print("[ERROR] Title not found in index and no close match.")
                return jsonify({"error": f"Movie '{title}' not found in index."}), 404

        idx = title_to_index[title]
        query_vector = index.reconstruct(idx).reshape(1, -1)

        # 🚩 Increase candidate pool to improve chance of getting enough valid recommendations (may include duplicates in pool)
        D, I = index.search(query_vector, num_results + 100)

        related_results = []
        seen = set()
        for score, i in zip(D[0], I[0]):
            if i == idx or i >= len(df) or i in seen:
                continue

            movie = df.iloc[i]
            # 🚩 Toggle this line to filter out movies with runtime <= 40 minutes
            if pd.notna(movie.get('runtime')) and float(movie.get('runtime', 0)) <= 40:
                continue

            if genre and genre not in str(movie.get('genres', '')).lower():
                continue

            poster = movie.get('poster_path', '')
            # Handle NaN poster
            poster = '' if pd.isna(poster) else poster

            related_results.append({
            'title': movie.get('title') or '',
            'overview': movie.get('overview') or '',
            'vote_average': float(movie.get('vote_average')) if pd.notna(movie.get('vote_average')) else 0.0,
            'popularity': float(movie.get('popularity')) if pd.notna(movie.get('popularity')) else 0.0,
            'genres': movie.get('genres') if pd.notna(movie.get('genres')) else '',
            'poster_path': movie.get('poster_path') if pd.notna(movie.get('poster_path')) else '',
            'similarity_score': float(score), # Store raw score for sorting
            'similarity': f"{round(float(score) * 100, 2)}%",
            'adult': str(movie.get('adult', 'FALSE')).upper(),
            'release_date': movie.get('release_date') if pd.notna(movie.get('release_date')) else 'N/A',
            'runtime': int(movie.get('runtime')) if pd.notna(movie.get('runtime')) else 0,
            'tagline': movie.get('tagline') if pd.notna(movie.get('tagline')) else '',
            'production_companies': movie.get('production_companies') if pd.notna(movie.get('production_companies')) else '',
            'backdrop_path': movie.get('backdrop_path') if pd.notna(movie.get('backdrop_path')) else ''
            })

            seen.add(i)
            # Collect more candidates than needed to allow for sorting
            if len(related_results) >= num_results * 2:
                break

        # Sort by similarity (desc) then by vote_average (desc)
        related_results.sort(key=lambda x: (x['similarity_score'], x['vote_average']), reverse=True)
        
        # Trim to requested limit
        related_results = related_results[:num_results]

        # Add the exact movie on top
        main_movie = df.iloc[idx]
        exact_result = {
            'title': main_movie.get('title') or '',
            'overview': main_movie.get('overview') or '',
            'vote_average': float(main_movie.get('vote_average')) if pd.notna(main_movie.get('vote_average')) else 0.0,
            'popularity': float(main_movie.get('popularity')) if pd.notna(main_movie.get('popularity')) else 0.0,
            'genres': main_movie.get('genres') if pd.notna(main_movie.get('genres')) else '',
            'poster_path': main_movie.get('poster_path') if pd.notna(main_movie.get('poster_path')) else '',
            'similarity_score': 1.0,
            'similarity': "100%",
            'adult': str(main_movie.get('adult', 'FALSE')).upper(),
            'release_date': main_movie.get('release_date') if pd.notna(main_movie.get('release_date')) else 'N/A',
            'runtime': int(main_movie.get('runtime')) if pd.notna(main_movie.get('runtime')) else 0,
            'tagline': main_movie.get('tagline') if pd.notna(main_movie.get('tagline')) else '',
            'production_companies': main_movie.get('production_companies') if pd.notna(main_movie.get('production_companies')) else '',
            'backdrop_path': main_movie.get('backdrop_path') if pd.notna(main_movie.get('backdrop_path')) else ''
        }

        return jsonify({"results": [exact_result] + related_results, "count": len(related_results) + 1})

    except Exception as e:
        print("[EXCEPTION]", e)
        return jsonify({"error": "Internal server error.", "details": str(e)}), 500

@app.route('/movie_detail')
def movie_detail():
    title = request.args.get('title', '').strip().lower()
    if not title or title not in title_to_index:
        return "Movie not found", 404

    idx = title_to_index[title]
    movie = df.iloc[idx]

    return render_template('movie_detail.html', movie=movie)

if __name__ == '__main__':
    app.run(debug=True)
