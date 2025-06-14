from flask import Flask, request, jsonify
from sklearn.metrics.pairwise import linear_kernel
from data_loader import get_data
from flask import Flask, render_template
import pandas as pd

app = Flask(__name__)

df, embeddings, title_to_index, index = get_data()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/smart_recommend', methods=['GET'])
def smart_recommend():
    title = request.args.get('title', '').strip().lower()
    genre = request.args.get('genre', '').strip().lower()
    num_results = int(request.args.get('limit', 10))

    if not title or title not in title_to_index:
        return jsonify({"error": "Valid and existing 'title' required."}), 400

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
            'title': movie.get('title'),
            'overview': movie.get('overview'),
            'vote_average': movie.get('vote_average'),
            'popularity': movie.get('popularity'),
            'genres': movie.get('genres'),
            'poster_path': movie.get('poster_path'),
            'similarity': round(float(score), 3)
        })

        if len(results) >= num_results:
            break

    if not results:
        return jsonify({"message": "No similar movies found for the given genre."}), 404

    return jsonify({"results": results, "count": len(results)})

if __name__ == '__main__':
    app.run(debug=True)