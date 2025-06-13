# app.py
from flask import Flask, request, jsonify, render_template
from data_loader import get_data
import pandas as pd

app = Flask(__name__)

df, faiss_index, embeddings, indices = get_data()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/smart_recommend', methods=['GET'])
def smart_recommend():
    title = request.args.get('title', '').strip().lower()
    genre = request.args.get('genre', '').strip().lower()
    num_results = int(request.args.get('limit', 10))

    if not title:
        return jsonify({"error": "Valid 'title' parameter is required."}), 400
    if title not in indices:
        return jsonify({"error": "Movie title not found in dataset."}), 404

    idx = indices[title]
    if isinstance(idx, pd.Series):
        idx = idx.iloc[0]
    if idx < 0 or idx >= len(df):
        return jsonify({"error": "Movie title index is invalid."}), 404

    # Search using FAISS
    D, I = faiss_index.search(embeddings[[idx]], num_results + 10)  # Get more in case of filtering
    sim_indices = I[0]
    sim_scores = D[0]

    recommendations = []
    for i, score in zip(sim_indices, sim_scores):
        if i == idx or i >= len(df):
            continue

        movie_genres = str(df.iloc[i].get('genres', '')).lower()
        if genre in movie_genres or not genre:
            movie_data = df.iloc[i][[
                'title', 'overview', 'vote_average',
                'popularity', 'genres', 'poster_path'
            ]].to_dict()
            movie_data = {k: (None if pd.isna(v) else v) for k, v in movie_data.items()}
            movie_data['similarity'] = round(float(score), 3)
            recommendations.append(movie_data)

        if len(recommendations) >= num_results:
            break

    if not recommendations:
        return jsonify({"message": "No similar movies found for the given genre."}), 404

    return jsonify({"results": recommendations, "count": len(recommendations)})

if __name__ == '__main__':
    app.run(debug=True)
