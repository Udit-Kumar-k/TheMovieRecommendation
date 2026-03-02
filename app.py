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
        for item in tmdb_results:
            tmdb_id = item.get('id')
            title = item.get('title', '').lower()
            
            idx = None
            if tmdb_id:
                # Local dataset uses TMDB IDs in the 'id' column
                matches = df.index[df['id'].astype(str) == str(tmdb_id)].tolist()
                if matches:
                    idx = matches[0]
            
            # Fallback to title matching if ID wasn't found in our dataset
            if idx is None and title in title_to_index:
                 idx = title_to_index[title]
                 
            if idx is not None:
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
            matches = df.index[df['id'].astype(str) == str(movie_id)].tolist()
            if matches:
                idx = matches[0]
        
        if idx is None and title:
            if title in title_to_index:
                idx = title_to_index[title]

        if idx is None:
            print("[ERROR] Title/ID not found in index.")
            return jsonify({"error": f"Movie not found in index."}), 404

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
    
    # Use fuzzy matching to find similar titles
    all_titles = list(title_to_index.keys())
    
    # Calculate similarity scores
    similarities = []
    for title in all_titles:
        ratio = SequenceMatcher(None, query, title).ratio()
        if ratio > 0.5:  # Only include if more than 50% similar
            similarities.append((title, ratio))
    
    # Sort by similarity score (highest first) and return top 10
    similar_movies = sorted(similarities, key=lambda x: x[1], reverse=True)[:10]
    
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
