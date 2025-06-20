from flask import Flask, request, jsonify
from sklearn.metrics.pairwise import linear_kernel
from data_loader import get_data, get_basic_data
from flask import Flask, render_template
import pandas as pd

app = Flask(__name__)

USE_RECOMMENDATION = True # 🔁 Set to True only if you have FAISS files

if USE_RECOMMENDATION:
    df, embeddings, title_to_index, index = get_data()
else:
    df = get_basic_data()


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/smart_recommend', methods=['GET'])
def smart_recommend():
    try:
        title = request.args.get('title', '').strip().lower()
        genre = request.args.get('genre', '').strip().lower()
        num_results = int(request.args.get('limit', 10))

        print(f"[INFO] Searching for title: {title} | genre: {genre}")

        if not title:
            return jsonify({"error": "Missing 'title' parameter."}), 400

        if title not in title_to_index:
            print("[ERROR] Title not found in index.")
            return jsonify({"error": f"Movie '{title}' not found in index."}), 404

        idx = title_to_index[title]
        query_vector = embeddings[idx].reshape(1, -1)

        D, I = index.search(query_vector, num_results + 10)

        related_results = []
        seen = set()
        for score, i in zip(D[0], I[0]):
            if i == idx or i >= len(df) or i in seen:
                continue

            movie = df.iloc[i]
            if genre and genre not in str(movie.get('genres', '')).lower():
                continue

            related_results.append({
                'title': movie.get('title') or '',
                'overview': movie.get('overview') or '',
                'vote_average': movie.get('vote_average') if pd.notna(movie.get('vote_average')) else 0.0,
                'popularity': movie.get('popularity') if pd.notna(movie.get('popularity')) else 0.0,
                'genres': movie.get('genres') or '',
                'poster_path': movie.get('poster_path') if pd.notna(movie.get('poster_path')) else '',
                'similarity': round(float(score), 3)
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
            'similarity': 1.0
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