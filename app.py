from flask import Flask, request, jsonify
from sklearn.metrics.pairwise import linear_kernel
from data_loader import get_data

app = Flask(__name__)

# Load once from separate module
df, tfidf_matrix, indices = get_data()

@app.route('/smart_recommend', methods=['GET'])
def smart_recommend():
    title = request.args.get('title', '').strip().lower()
    genre = request.args.get('genre', '').strip().lower()
    num_results = int(request.args.get('limit', 10))

    if not title or title not in indices:
        return jsonify({"error": "Valid 'title' parameter is required."}), 400

    idx = indices[title]
    sim_scores = linear_kernel(tfidf_matrix[idx], tfidf_matrix).flatten()
    sim_indices = sim_scores.argsort()[::-1][1:]

    recommendations = []
    for i in sim_indices:
        movie_genres = str(df.iloc[i]['genres']).lower()
        if genre in movie_genres or not genre:
            movie_data = df.iloc[i][['title', 'overview', 'vote_average', 'popularity', 'genres', 'poster_path']].to_dict()
            movie_data['similarity'] = round(float(sim_scores[i]), 3)
            recommendations.append(movie_data)
        if len(recommendations) >= num_results:
            break

    if not recommendations:
        return jsonify({"message": "No similar movies found for the given genre."})

    return jsonify({"results": recommendations, "count": len(recommendations)})

if __name__ == '__main__':
    app.run(debug=True)
