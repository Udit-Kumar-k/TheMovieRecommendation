from flask import Flask, request, jsonify
from sklearn.metrics.pairwise import linear_kernel
from data_loader import get_data, get_basic_data
from flask import Flask, render_template
import pandas as pd

app = Flask(__name__)

USE_RECOMMENDATION = True  # 🔁 Set to True only if you have FAISS files

if USE_RECOMMENDATION:
    df, embeddings, title_to_index, index = get_data()
else:
    df = get_basic_data()


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/smart_recommend', methods=['GET'])
def smart_recommend():
    title = request.args.get('title', '').strip().lower()
    genre = request.args.get('genre', '').strip().lower()
    num_results = int(request.args.get('limit', 10))

    if not title:
        return jsonify({"error": "Missing 'title' parameter."}), 400

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

        poster = movie.get('poster_path', '')
        # Handle NaN poster
        poster = '' if pd.isna(poster) else poster

        results.append({
        'title': movie.get('title') or '',
        'overview': movie.get('overview') or '',
        'vote_average': movie.get('vote_average') if pd.notna(movie.get('vote_average')) else 0.0,
        'popularity': movie.get('popularity') if pd.notna(movie.get('popularity')) else 0.0,
        'genres': movie.get('genres') or '',
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