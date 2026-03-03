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
        seen_indices = set()
        
        for item in tmdb_results:
            tmdb_id = item.get('id')
            title = item.get('title', '').lower()
            
            idx = None
            if tmdb_id:
                # O(1) lookup using pre-built dictionary
                idx = id_to_index.get(str(tmdb_id))
            
            # Fallback to title matching if ID wasn't found in our dataset
            if idx is None and title in title_to_index:
                 idx = title_to_index[title]
                 
            if idx is not None and idx not in seen_indices:
                 seen_indices.add(idx)
                 movie = df.iloc[idx]
                 
                 enriched_results.append({
                    'id': str(movie.get('id', tmdb_id)),
                    'title': movie.get('title') or item.get('title'),
                    'overview': movie.get('overview') or item.get('overview', ''),
                    'vote_average': movie.get('vote_average') if pd.notna(movie.get('vote_average')) else item.get('vote_average', 0.0),
                    'popularity': movie.get('popularity') if pd.notna(movie.get('popularity')) else item.get('popularity', 0.0),
                    'genres': movie.get('genres') or '',
                    'poster_path': movie.get('poster_path') if pd.notna(movie.get('poster_path')) else item.get('poster_path', ''),
                    'similarity': "Search Match",
                    'adult': str(movie.get('adult', item.get('adult', 'FALSE'))).upper(),
                    'is_search_result': True # Flag to differentiate from recommendations
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

        print(f"[INFO] Searching for title: {title} | id: {movie_id} | genre: {genre}")

        if not title and not movie_id:
            return jsonify({"error": "Missing 'title' or 'id' parameter."}), 400

        idx = None
        if movie_id:
            idx = id_to_index.get(str(movie_id))
        
        if idx is None and title:
            if title in title_to_index:
                idx = title_to_index[title]

        if idx is None:
            print("[ERROR] Title/ID not found in index.")
            return jsonify({"error": f"Movie not found in index."}), 404

        idx = int(idx)
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
            'id': str(movie.get('id', '')),
            'title': movie.get('title') or '',
            'overview': movie.get('overview') or '',
            'vote_average': movie.get('vote_average') if pd.notna(movie.get('vote_average')) else 0.0,
            'popularity': movie.get('popularity') if pd.notna(movie.get('popularity')) else 0.0,
            'genres': movie.get('genres') or '',
            'poster_path': movie.get('poster_path') if pd.notna(movie.get('poster_path')) else '',
            'similarity': f"{round(float(score) * 100, 2)}%",
            'adult': str(movie.get('adult', 'FALSE')).upper()  # 🚩 Imprinting: Pass 'adult' flag to frontend for 18+ icon logic
            })

            seen.add(i)
            if len(related_results) >= num_results:
                break

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
