from flask import Flask, request, jsonify
from sklearn.metrics.pairwise import linear_kernel
from data_loader import get_data
from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

# Load once from separate module
df, tfidf_matrix, indices = get_data()

@app.route('/smart_recommend', methods=['GET'])
def smart_recommend():
    title = request.args.get('title', '').strip().lower()
    genre = request.args.get('genre', '').strip().lower()
    num_results = int(request.args.get('limit', 10))

    # Check if title exists in dataset
    if not title:
        return jsonify({"error": "Valid 'title' parameter is required."}), 400

    if title not in indices:
        return jsonify({"error": "Movie title not found in dataset."}), 404

    idx = indices[title]


    if not isinstance(idx, int) or idx < 0 or idx >= len(df):
        return jsonify({"error": "Movie title index is invalid."}), 404

    # Compute similarity scores
    sim_scores = linear_kernel(tfidf_matrix[idx], tfidf_matrix).flatten()
    sim_indices = sim_scores.argsort()[::-1][1:]  # skip the movie itself

    recommendations = []
    for i in sim_indices:
        if i >= len(df):
            continue  # avoid out-of-bounds error

        movie_genres = str(df.iloc[i].get('genres', '')).lower()

        # Check genre filter or skip if not matched
        if genre in movie_genres or not genre:
            movie_data = df.iloc[i][[
                'title', 'overview', 'vote_average',
                'popularity', 'genres', 'poster_path'
            ]].to_dict()
            movie_data['similarity'] = round(float(sim_scores[i]), 3)
            recommendations.append(movie_data)

        if len(recommendations) >= num_results:
            break

    if not recommendations:
        return jsonify({"message": "No similar movies found for the given genre."}), 404

    return jsonify({"results": recommendations, "count": len(recommendations)})


if __name__ == '__main__':
    app.run(debug=True)
