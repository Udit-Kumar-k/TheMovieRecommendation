from flask import Flask, request, jsonify, render_template
from sklearn.metrics.pairwise import linear_kernel
from data_loader import get_data, get_basic_data
import pandas as pd
import difflib

app = Flask(__name__)

USE_RECOMMENDATION = False  # Set to True only if you have FAISS files

if USE_RECOMMENDATION:
    df, embeddings, title_to_index, index = get_data()
else:
    df = get_basic_data()

# Create a list of all movie titles for autocomplete
movie_titles = df['title'].dropna().str.lower().unique().tolist()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    """Return movie title suggestions based on partial input"""
    query = request.args.get('q', '').strip().lower()
    limit = int(request.args.get('limit', 10))
    
    if not query:
        return jsonify({"suggestions": []})
    
    # Find titles that start with the query (priority)
    starts_with = [title for title in movie_titles if title.startswith(query)]
    
    # Find titles that contain the query
    contains = [title for title in movie_titles if query in title and not title.startswith(query)]
    
    # Use difflib for fuzzy matching if we need more results
    if len(starts_with) + len(contains) < limit:
        fuzzy_matches = difflib.get_close_matches(query, movie_titles, n=limit, cutoff=0.6)
        fuzzy_matches = [title for title in fuzzy_matches if title not in starts_with and title not in contains]
    else:
        fuzzy_matches = []
    
    # Combine results with priority order
    suggestions = (starts_with + contains + fuzzy_matches)[:limit]
    
    return jsonify({
        "suggestions": suggestions,
        "query": query
    })

@app.route('/search', methods=['GET'])
def search_movies():
    """Search for movies by title"""
    query = request.args.get('q', '').strip().lower()
    
    if not query:
        return jsonify({"error": "Missing query parameter"}), 400
    
    # Find exact or close matches
    matches = df[df['title'].str.lower().str.contains(query, na=False)]
    
    results = []
    for _, movie in matches.head(20).iterrows():
        results.append({
            'title': movie.get('title', ''),
            'overview': movie.get('overview', ''),
            'vote_average': movie.get('vote_average') if pd.notna(movie.get('vote_average')) else 0.0,
            'popularity': movie.get('popularity') if pd.notna(movie.get('popularity')) else 0.0,
            'genres': movie.get('genres', ''),
            'poster_path': movie.get('poster_path') if pd.notna(movie.get('poster_path')) else '',
            'release_date': movie.get('release_date', '')
        })
    
    return jsonify({"results": results, "count": len(results)})

@app.route('/smart_recommend', methods=['GET'])
def smart_recommend():
    title = request.args.get('title', '').strip().lower()
    genre = request.args.get('genre', '').strip().lower()
    num_results = int(request.args.get('limit', 10))

    if not title:
        return jsonify({"error": "Missing 'title' parameter."}), 400

    # Check if recommendation system is available
    if not USE_RECOMMENDATION:
        return jsonify({"error": "Recommendation system not available. Please set USE_RECOMMENDATION=True and ensure FAISS files exist."}), 503

    if title not in title_to_index:
        return jsonify({"error": f"Movie '{title}' not found in index."}), 404

    idx = title_to_index[title]
    query_vector = embeddings[idx].reshape(1, -1)

    D, I = index.search(query_vector, num_results + 10)

    results = []
    for score, i in zip(D[0], I[0]):
        if i == idx or i >= len(df):
            continue

        movie = df.iloc[i]
        if genre and genre not in str(movie.get('genres', '')).lower():
            continue

        results.append({
            'title': movie.get('title', ''),
            'overview': movie.get('overview', ''),
            'vote_average': movie.get('vote_average') if pd.notna(movie.get('vote_average')) else 0.0,
            'popularity': movie.get('popularity') if pd.notna(movie.get('popularity')) else 0.0,
            'genres': movie.get('genres', ''),
            'poster_path': movie.get('poster_path') if pd.notna(movie.get('poster_path')) else '',
            'similarity': round(float(score), 3)
        })

        if len(results) >= num_results:
            break

    if not results:
        return jsonify({"message": "No similar movies found for the given genre."}), 404

    return jsonify({"results": results, "count": len(results)})

if __name__ == '__main__':
    app.run(debug=True)