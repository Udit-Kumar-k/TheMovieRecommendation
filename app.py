from flask import Flask, request, jsonify
from sklearn.metrics.pairwise import linear_kernel
from data_loader import get_data, get_basic_data
from flask import Flask, render_template
import pandas as pd
from rapidfuzz import process, fuzz

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
            'similarity': f"{round(float(score) * 100, 2)}%"
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
            'similarity': "100%"
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

    matches = []
    count = 0
    for title, idx in title_to_index.items():
        if query in title:
            movie = df.iloc[idx]
            year = ''
            director = ''
            # Try to extract year and director if available
            if 'release_date' in movie and pd.notna(movie['release_date']):
                year = str(movie['release_date'])[:4]
            if 'director' in movie and pd.notna(movie['director']):
                director = movie['director']
            matches.append({
                'title': movie.get('title', ''),
                'year': year,
                'director': director
            })
            count += 1
            if count >= 20:
                break
    return jsonify(matches)

@app.route('/all_titles', methods=['GET'])
def all_titles():
    movies = []
    for idx, row in df.iterrows():
        year = ''
        director = ''
        if 'release_date' in row and pd.notna(row['release_date']):
            year = str(row['release_date'])[:4]
        if 'director' in row and pd.notna(row['director']):
            director = row['director']
        movies.append({
            'title': row.get('title', ''),
            'year': year,
            'director': director
        })
    return jsonify(movies)

@app.route('/movie_detail')
def movie_detail():
    title = request.args.get('title', '').strip().lower()
    if not title or title not in title_to_index:
        return "Movie not found", 404

    idx = title_to_index[title]
    movie = df.iloc[idx]

    return render_template('movie_detail.html', movie=movie)

@app.route('/suggest_fuzzy', methods=['GET'])
def suggest_fuzzy():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])
    # Filter titles that contain the query substring (case-insensitive)
    filtered = df[df['title'].str.lower().str.contains(query, na=False)].copy()
    if filtered.empty:
        return jsonify([])  # No matches, return empty list

    # Prepare choices: list of (title, index)
    choices = [(row['title'], idx) for idx, row in filtered.iterrows() if pd.notna(row['title'])]

    # Use rapidfuzz to get top 20 matches
    results = process.extract(
        query,
        choices,
        scorer=fuzz.WRatio,
        limit=20
    )
    matches = []
    for (match_title, idx), score, _ in results:
        movie = filtered.loc[idx]
        # Extract year from release_date (last 4 chars)
        year = 'Unknown'
        if pd.notna(movie.get('release_date', None)):
            date_str = str(movie['release_date'])
            if len(date_str) >= 4:
                year_candidate = date_str[-4:]
                if year_candidate.isdigit() and year_candidate != 'XXXX':
                    year = year_candidate
        # Extract director
        director = movie.get('director', 'Unknown') or 'Unknown'
        matches.append({
            'title': match_title,
            'year': year,
            'director': director
        })
    return jsonify(matches)

if __name__ == '__main__':
    app.run(debug=True)
