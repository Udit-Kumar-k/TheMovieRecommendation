from flask import Flask, request, jsonify
from sklearn.metrics.pairwise import linear_kernel
from data_loader import get_data, get_basic_data
from flask import Flask, render_template
import pandas as pd
from difflib import SequenceMatcher

app = Flask(__name__)

import os
import requests
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)
print(f"Loaded .env from {env_path}")
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
print(f"Global API Key is: {'*'*5 + TMDB_API_KEY[-4:] if TMDB_API_KEY else 'None'}")

USE_RECOMMENDATION = True # 🔁 Set to True only if you have FAISS files

if USE_RECOMMENDATION:
    df, title_to_index, index = get_data()
else:
    df = get_basic_data()

print("[INFO] Building id_to_index map for O(1) lookups...")
id_to_index = {}
for i, id_val in enumerate(df['id']):
    if pd.notna(id_val):
        # The CSV load sometimes parses ID as float due to NaNs, safely cast to int then str
        try:
            str_id = str(int(float(id_val)))
            id_to_index[str_id] = i
        except ValueError:
            id_to_index[str(id_val)] = i
print(f"[INFO] Map built with {len(id_to_index)} entries!")

@app.route('/enrich_tmdb_results', methods=['POST'])
def enrich_tmdb_results():
    """
    Receives raw TMDB search results from the frontend and matches them
    against our local dataset, returning the full rich movie objects.
    """
    try:
        data = request.json
        tmdb_results = data.get('results', [])
        
        enriched_results = []
        seen_tmdb_ids = set()
        
        for item in tmdb_results:
            tmdb_id = str(item.get('id', ''))
            
            if not tmdb_id or tmdb_id in seen_tmdb_ids:
                continue
            seen_tmdb_ids.add(tmdb_id)
            
            idx = id_to_index.get(tmdb_id)
                 
            if idx is not None:
                 movie = df.iloc[idx]
                 
                 enriched_results.append({
                    'id': str(movie.get('id', tmdb_id)),
                    'title': item.get('title') or movie.get('title'), # Prefer TMDB for display
                    'overview': item.get('overview') or movie.get('overview', ''),
                    'vote_average': item.get('vote_average') if item.get('vote_average') else (movie.get('vote_average') if pd.notna(movie.get('vote_average')) else 0.0),
                    'popularity': item.get('popularity') if item.get('popularity') else (movie.get('popularity') if pd.notna(movie.get('popularity')) else 0.0),
                    'genres': movie.get('genres') or '',
                    'poster_path': item.get('poster_path') if item.get('poster_path') else (movie.get('poster_path') if pd.notna(movie.get('poster_path')) else ''),
                    'similarity': "Search Match",
                    'adult': str(item.get('adult', movie.get('adult', 'FALSE'))).upper(),
                    'is_search_result': True,
                    'in_index': True
                })
            else:
                # Still include the TMDB result even if not in our DB so users can find very obscure/new movies!
                enriched_results.append({
                    'id': str(tmdb_id),
                    'title': item.get('title'),
                    'overview': item.get('overview', ''),
                    'vote_average': item.get('vote_average', 0.0),
                    'popularity': item.get('popularity', 0.0),
                    'genres': '', # We don't have local genres for this
                    'poster_path': item.get('poster_path', ''),
                    'similarity': "Search Match",
                    'adult': str(item.get('adult', 'FALSE')).upper(),
                    'is_search_result': True,
                    'in_index': False
                })
        return jsonify({"results": enriched_results, "count": len(enriched_results)})

    except Exception as e:
        print(f"[ERROR] Enriching TMDB results failed: {e}")
        return jsonify({"error": "Failed to enrich TMDB data"}), 500


@app.route('/')
def home():
    load_dotenv()
    api_key = os.getenv('TMDB_API_KEY')
    return render_template('index.html', tmdb_api_key=api_key)

@app.route('/smart_recommend', methods=['GET'])
def smart_recommend():
    try:
        title = request.args.get('title', '').strip().lower()
        movie_id = request.args.get('id', '').strip()
        genre = request.args.get('genre', '').strip().lower()
        num_results = int(request.args.get('limit', 30))  # Default to 30
        sort_mode = request.args.get('sort', 'similarity').strip().lower()

        print(f"[INFO] Searching for title: {title} | id: {movie_id} | genre: {genre} | sort: {sort_mode}")

        if not title and not movie_id:
            return jsonify({"error": "Missing 'title' or 'id' parameter."}), 400

        idx = None
        if movie_id:
            idx = id_to_index.get(str(movie_id))
            if idx is None:
                # If an exact ID is provided and we don't have it, don't fall back to title.
                # Title fallback merges unrelated movies (e.g. "Secret Agent 2025" vs "Secret Agent 1996").
                print(f"[ERROR] Movie ID {movie_id} not found in index.")
                return jsonify({"error": f"Movie ID not found in index."}), 404
        elif title:
            if title in title_to_index:
                idx = title_to_index[title]

        if idx is None:
            print("[ERROR] Title/ID not found in index.")
            return jsonify({"error": f"Movie not found in index."}), 404

        idx = int(idx)
        query_vector = index.reconstruct(idx).reshape(1, -1)
        
        main_movie = df.iloc[idx]
        query_genres_raw = main_movie.get('genres', '')
        if isinstance(query_genres_raw, list):
            query_genres = set(g.strip().lower() for g in query_genres_raw if g and isinstance(g, str))
        else:
            query_genres_str = str(query_genres_raw)
            query_genres = set(g.strip().lower() for g in query_genres_str.split(',') if g.strip()) if query_genres_str else set()

        # 🚩 Increase candidate pool drastically to allow for quality sorting
        pool_size = num_results * 15 
        D, I = index.search(query_vector, pool_size)

        candidate_movies = []
        seen = set()
        for score, i in zip(D[0], I[0]):
            if i == idx or i >= len(df) or i in seen:
                continue

            movie = df.iloc[i]
            if pd.notna(movie.get('runtime')) and float(movie.get('runtime', 0)) <= 40:
                continue

            if genre and genre not in str(movie.get('genres', '')).lower():
                continue
            
            seen.add(i)
            # Math: similarity is 0 to 1 usually (inner product on normalized vectors), popularity can be 0 or 100+, vote_average is 0 to 10
            vote = float(movie.get('vote_average') if pd.notna(movie.get('vote_average')) else 0.0)
            pop = float(movie.get('popularity') if pd.notna(movie.get('popularity')) else 0.0)
            cosine_sim = float(score)
            
            # --- Genre Jaccard Boost Logic ---
            cand_genres_raw = movie.get('genres', '')
            if isinstance(cand_genres_raw, list):
                cand_genres = set(g.strip().lower() for g in cand_genres_raw if g and isinstance(g, str))
            else:
                cand_genres_str = str(cand_genres_raw)
                cand_genres = set(g.strip().lower() for g in cand_genres_str.split(',') if g.strip()) if cand_genres_str else set()
            
            if query_genres and cand_genres:
                intersect = len(query_genres.intersection(cand_genres))
                union = len(query_genres.union(cand_genres))
                genre_jaccard = intersect / union if union > 0 else 0.0
            else:
                genre_jaccard = 0.0
                
            # Compute new soft-boosted similarity score
            # User Constraints: 0.85 * cosine_sim + 0.15 * genre_jaccard
            final_sim = (0.85 * cosine_sim) + (0.15 * genre_jaccard)
            
            # Additional heuristic scoring for 'quality'
            import math
            pop_score = math.log1p(pop) / 10.0 # scales popularity down
            vote_score = vote / 10.0
            
            # Filter pool to generally good/relevant movies
            # Tweak: 85% weight on similarity to prevent popular but completely unrelated movies (e.g. American Beauty) 
            # from brute-forcing their way into the candidate pool. 
            combined_score = (final_sim * 0.85) + (vote_score * 0.05) + (pop_score * 0.10)

            candidate_movies.append({
                'movie': movie,
                'similarity_val': final_sim,
                'combined_score': combined_score,
                'vote': vote
            })

        # Base pool selected by combined score so we still avoid obscure garbage
        candidate_movies.sort(key=lambda x: x['combined_score'], reverse=True)
        top_candidates = candidate_movies[:num_results]

        # Then apply the user's specific sort preference over this clean pool
        if sort_mode == 'quality':
            top_candidates.sort(key=lambda x: x['vote'], reverse=True)
        else: # 'similarity' default
            top_candidates.sort(key=lambda x: x['similarity_val'], reverse=True)
        
        related_results = []
        for item in top_candidates:
            movie = item['movie']
            sim_val = item['similarity_val']
            
            poster = movie.get('poster_path', '')
            poster = '' if pd.isna(poster) else poster

            related_results.append({
                'id': str(movie.get('id', '')),
                'title': movie.get('title') or '',
                'overview': movie.get('overview') or '',
                'vote_average': movie.get('vote_average') if pd.notna(movie.get('vote_average')) else 0.0,
                'popularity': movie.get('popularity') if pd.notna(movie.get('popularity')) else 0.0,
                'genres': movie.get('genres') or '',
                'poster_path': poster,
                'similarity': f"{round(sim_val * 100, 2)}%",
                'adult': str(movie.get('adult', 'FALSE')).upper() 
            })

        # Add the exact movie on top
        main_movie = df.iloc[idx]
        exact_result = {
            'id': str(main_movie.get('id', '')),
            'title': main_movie.get('title') or '',
            'overview': main_movie.get('overview') or '',
            'vote_average': main_movie.get('vote_average') if pd.notna(main_movie.get('vote_average')) else 0.0,
            'popularity': main_movie.get('popularity') if pd.notna(main_movie.get('popularity')) else 0.0,
            'genres': main_movie.get('genres') or '',
            'poster_path': main_movie.get('poster_path') if pd.notna(main_movie.get('poster_path')) else '',
            'similarity': "100%",
            'adult': str(main_movie.get('adult', 'FALSE')).upper()  # 🚩 Imprinting: Pass 'adult' flag to frontend for 18+ icon logic
        }

        return jsonify({"results": [exact_result] + related_results, "count": len(related_results) + 1})

    except Exception as e:
        print("[EXCEPTION]", e)
        return jsonify({"error": "Internal server error.", "details": str(e)}), 500



@app.route('/suggest', methods=['GET'])
def suggest():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])

    matches = [title for title in title_to_index.keys() if query in title]
    return jsonify(matches[:10])

@app.route('/find_similar_movies', methods=['GET'])
def find_similar_movies():
    """Find movies with similar names using fuzzy matching"""
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])
    
    # Check if exact match exists first
    if query in title_to_index:
        return jsonify([])  # Exact match found, no suggestions needed
    
    # Use C-optimized fuzzy matching to find similar titles
    all_titles = list(title_to_index.keys())
    
    import difflib
    matches = difflib.get_close_matches(query, all_titles, n=10, cutoff=0.5)
    similar_movies = [(m, SequenceMatcher(None, query, m).ratio()) for m in matches]
    
    results = []
    for title, score in similar_movies:
        idx = title_to_index[title]
        movie = df.iloc[idx]
        results.append({
            'title': title,
            'display_title': movie.get('title', title),
            'similarity_score': round(score * 100, 1),
            'poster_path': movie.get('poster_path', ''),
            'year': str(movie.get('release_date', 'N/A'))[:4] if pd.notna(movie.get('release_date')) else 'N/A'
        })
    
    return jsonify(results)

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    idx = None
    if movie_id in id_to_index:
        idx = id_to_index[movie_id]
        
    if idx is None:
        dummy_movie = {'id': movie_id, 'title': 'Movie Not Found', 'release_date': '', 'vote_average': 0.0, 'runtime': 0, 'genres': '', 'overview': ''}
        return render_template('movie_detail.html', movie=dummy_movie, tmdb_api_key=os.getenv('TMDB_API_KEY'), error=True, original_title=movie_id)

    movie_series = df.iloc[idx]
    
    movie = {
        'id': movie_id,
        'title': movie_series.get('title', ''),
        'release_date': str(movie_series.get('release_date', '')) if pd.notna(movie_series.get('release_date')) else '',
        'vote_average': float(movie_series.get('vote_average', 0.0)) if pd.notna(movie_series.get('vote_average')) else 0.0,
        'runtime': int(movie_series.get('runtime', 0)) if pd.notna(movie_series.get('runtime')) else 0,
        'genres': movie_series.get('genres', '') if pd.notna(movie_series.get('genres')) else '',
        'overview': movie_series.get('overview', '') if pd.notna(movie_series.get('overview')) else ''
    }
    
    # We pass the ID and Title. The frontend template will do the heavy lifting of fetching
    # high-res TMDB metadata, cast, and trailers securely.
    api_key = os.getenv('TMDB_API_KEY')
    return render_template('movie_detail.html', movie=movie, tmdb_api_key=api_key, error=False)

if __name__ == '__main__':
    app.run(debug=True)
