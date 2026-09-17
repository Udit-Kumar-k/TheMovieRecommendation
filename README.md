---
title: MoviesIndex
emoji: 🎥
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

# MovieRec

A semantic movie recommendation engine. You search for a movie you love, it finds you movies that feel like it — same themes, same tone, similar plot — not because they share a genre tag or both got popular in the same year.

https://uditkumar-moviesindex.hf.space


## What it does

Most recommendation systems work on co-watch patterns or genre buckets. This one encodes each movie as a semantic vector from its plot, genres, and keywords, then uses approximate nearest-neighbour search to find films that are genuinely close in meaning.

You get a poster, a description, and a trailer link. You decide whether to watch. No score, no algorithm deciding for you.


## Features

**Search**
- Semantic similarity search over ~90k movies using FAISS + MiniLM sentence embeddings
- Genre Jaccard re-ranking on top of cosine similarity (validated +2.8pp domain relevance in ablation tests)
- Quality filters: removes shorts, unrated obscurities, TV movies, documentaries
- Three sort modes: Similarity, Quality (vote-weighted), Strict Genre Match
- "Did you mean?" fuzzy fallback when a title isn't in the index
- TMDB API toggle to compare our results against TMDB's own recommendation engine live

**Pool Mode**
- Pick up to 5 movies, get recommendations at the centroid of their embedding vectors
- Useful when you want something "between *No Country for Old Men* and *Parasite*" — a single anchor can't express that
- Pool state persists in localStorage across sessions; slots can be edited or removed individually

**Watchlist**
- Save movies while browsing; synced to your account via MongoDB
- Accessible from any device after signing in
- Add from search results, recommendations, or the detail page

**Auth**
- Sign in with Google — no username or password
- JWT issued server-side, stored in localStorage; you stay logged in across tabs and browser restarts

**Movie detail pages**
- Full cast, crew, trailer embed, keywords, budget, box office, tagline
- Watchlist button directly on the detail page
- 18+ badge instead of poster for adult-flagged titles

**Index updates**
- GitHub Actions workflow runs every Sunday at midnight UTC
- Fetches new movies from TMDB's Discover API, merges them, and incrementally updates the FAISS index
- Automatically pushes the updated index to Hugging Face Spaces


## How it works

```
User searches for a movie title
        │
        ▼
TMDB Live Search → user selects the exact film
        │
        ▼
FAISS nearest-neighbour (pool of 750 candidates from 384-dim MiniLM vectors)
        │
        ▼
Genre Jaccard re-ranking (+25% weight toward genre-aligned results)
        │
        ▼
Quality filters (runtime, vote count, popularity, genre exclusions)
        │
        ▼
Sort: Similarity | Quality | Strict Genre Match
        │
        ▼
Top 50 results — posters, ratings, and metadata fetched live from TMDB
```

**Pool Mode** works the same way, except the query vector is the L2-normalised mean of up to 5 selected movie vectors retrieved directly from the loaded FAISS index via `index.reconstruct()`.


## Performance

Benchmarked on a hand-curated golden dataset of 100 anchor movies across four difficulty tiers: franchise pairs (sanity checks), cross-genre semantic pairs, hard cases, and Bollywood/regional films.

| Model | Recall@5 | Recall@10 | nDCG@5 | nDCG@10 | MRR@5 | MRR@10 | Latency |
|---|---|---|---|---|---|---|---|
| **MiniLM** *(production)* | 16.3% | 20.0% | **0.277** | **0.279** | **0.262** | **0.266** | **1.64 ms** |
| MPNet | 16.4% | 20.5% | 0.253 | 0.277 | 0.238 | 0.251 | 10.38 ms |

MPNet edges ahead by ~1–2pp on raw Recall. MiniLM beats it on ranking quality (nDCG, MRR) and is 6× faster. Production uses MiniLM.

Recall numbers look modest because the evaluation targets hard semantic pairs, not obvious franchise sequels. A system that returns *Burning* for *Parasite* and *Force Majeure* for *A Separation* is doing real work. The 20 franchise pairs in the dataset are sanity checks and should be excluded from aggregate metrics when reporting real-world performance.

Full methodology in [`EVALUATION.md`](EVALUATION.md).


## Quick start

```bash
git clone https://github.com/Udit-Kumar-k/TheMovieRecommendation.git
cd TheMovieRecommendation
pip install -r requirements.txt

# Copy and fill in your env vars
cp .env.example .env

# Build the FAISS index (first run — ~30 min on CPU)
python build_index.py --model minilm --output-dir models/minilm

# Start the server
python app.py
```

Visit `http://localhost:5000`.


## Environment variables

| Variable | Required | Description |
|---|---|---|
| `TMDB_API_KEY` | ✅ | TMDB v3 API key — [get one free](https://www.themoviedb.org/settings/api) |
| `GOOGLE_CLIENT_ID` | ✅ | Google OAuth 2.0 client ID — [create at Google Cloud Console](https://console.cloud.google.com/); add your domain to Authorized JavaScript Origins |
| `MONGODB_URI` | ✅ | MongoDB connection string — MongoDB Atlas free tier works |
| `JWT_SECRET` | ✅ | Secret key for signing JWTs issued after Google sign-in |
| `HF_INDEX_DATASET` | Optional | Hugging Face dataset ID for remote index storage |
| `MODEL_PATH` | Optional | Override model directory (default: `models/minilm`) |
| `TMDB_API_BASE` | Optional | Override TMDB API host |


## Project structure

```
movierec/
├── app.py                  # Flask app — routes for search, recommendations, pool, watchlist, auth
├── build_index.py          # Build FAISS index from scratch (MiniLM or MPNet)
├── update_index.py         # Incremental index update (new movies only)
├── smart_tmdb_fetcher.py   # TMDB Discover API fetcher and dataset merger
├── data_loader.py          # Load FAISS index and DataFrame from disk
├── data_utils.py           # Dataset path resolution
│
├── models/
│   └── minilm/
│       ├── faiss.index     # Vector index (Git LFS)
│       └── index_data.pkl  # DataFrame and title→index map (Git LFS)
│
├── static/
│   ├── script.js           # Frontend — Search, Pool, Watchlist modes, Google OAuth, TMDB live fetch
│   ├── style.css           # All styles
│   └── icons/              # SVGs: search icon, fallback poster, 18+ badge
│
├── templates/
│   ├── index.html          # Main page — Search / Pool / Watchlist tabs, sign-in modal
│   └── movie_detail.html   # Full movie detail page with watchlist button
│
├── .github/workflows/
│   └── update_index.yml    # Weekly: fetch new TMDB movies, rebuild index, push to HF Spaces
│
├── bench_relevancy.py      # Recall / MRR / nDCG benchmark
├── bench_jaccard.py        # Genre boost ablation
├── bench_tmdb_overlap.py   # TMDB overlap reference
├── bench_latency.py        # MiniLM vs MPNet latency
├── get_metrics.py          # Clean metrics summary
│
├── golden_dataset.json     # 100-anchor hand-curated evaluation set
├── EVALUATION.md           # Full evaluation methodology and results
│
├── Dockerfile
├── requirements.txt
└── auto_sync.bat           # One-click local index update (Windows)
```


## Running benchmarks

```bash
python bench_relevancy.py                           # Recall, MRR, nDCG
python bench_jaccard.py --golden-file golden_dataset.json   # Genre boost ablation
python bench_tmdb_overlap.py                        # TMDB overlap comparison
python bench_latency.py                             # MiniLM vs MPNet latency
python get_metrics.py                               # Summary table
```


## Docker

```bash
docker build -t movierec .
docker run -p 5000:5000 \
  -e TMDB_API_KEY=your_key \
  -e GOOGLE_CLIENT_ID=your_client_id \
  -e MONGODB_URI=your_mongo_uri \
  -e JWT_SECRET=your_secret \
  movierec
```


## Tech stack

| Layer | Technology |
|---|---|
| Embeddings | `sentence-transformers` MiniLM-L6-v2 |
| Vector search | `faiss-cpu` IndexFlatIP (exact inner product) |
| Backend | Flask |
| Auth | Google Identity Services (GIS) OAuth 2.0 — JWT persisted in localStorage |
| User data | MongoDB Atlas — `users` and `watchlists` collections |
| Frontend | Vanilla JS + CSS, no framework |
| Metadata | TMDB API v3 (live, client-side) |
| App hosting | Hugging Face Spaces (Docker) |
| CI/CD | GitHub Actions — weekly index update + automatic HF Spaces deploy |


## Known limitations

- Recall is computed against one annotator's judgment. Multi-annotator evaluation with inter-rater agreement would be more rigorous.
- The index covers ~90k movies. Very obscure or very recently released films may not be present; the app falls back to TMDB's own recommendation API in that case.
- Metadata quality varies in the source dataset. Some older or non-English films have sparse keyword and genre data, which reduces retrieval quality for those titles.


## License

MIT