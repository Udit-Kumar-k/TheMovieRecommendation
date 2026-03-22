---
title: MoviesIndex
emoji: 🎥
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---
# 🎬 MovieRec — Semantic Movie Recommendation Engine

> *Find your next obsession. Not because it's popular — because it actually matches what you love.*


## What Is This?

MovieRec is a **production-grade semantic recommendation engine** that understands movies the way a film-literate human does — not by genre tags or co-watch patterns, but by the actual meaning and themes embedded in a film's DNA.

You search for *Parasite*. You get *Burning*, *Shoplifters*, *Memories of Murder* — not *Knives Out* because it's also a thriller that people watched in 2019.

Built on **FAISS vector search** + **sentence transformers**, with a clean Flask backend and a fully TMDB-integrated frontend.


## How It Works

Each movie is encoded as a high-dimensional semantic vector from its genres, keywords, and overview. When you search for a movie, the engine performs approximate nearest-neighbor lookup in a 90,000-movie FAISS index — returning films that are genuinely similar in theme, tone, and narrative structure.

On top of raw cosine similarity, a **25% Genre Jaccard boost** nudges results toward domain-relevant matches. This was validated in ablation testing: the boost moves genre alignment from ~92.1% → **98.7%** without sacrificing semantic diversity.

```
User query
    │
    ▼
TMDB Live Search → Enrich with local index → Select movie
    │
    ▼
FAISS nearest-neighbor (pool = 750 candidates)
    │
    ▼
Genre Jaccard re-ranking (+25% weight)
    │
    ▼
Quality filters (runtime, vote_count, popularity, genre exclusions)
    │
    ▼
Sort by: Similarity | Quality | Strict Genre Match
    │
    ▼
Results (top 50, rendered as poster grid with live TMDB metadata)
```


## Pool Mode — Taste Centroid Search

Pool Mode lets you describe your taste as a *combination* of up to 5 movies rather than a single anchor. "Give me something between *Parasite* and *No Country for Old Men*" is a more precise query than either film alone.

```
User selects up to 5 movies
    │
    ▼
Extract 384-dim vectors for each via index.reconstruct()
    │
    ▼
Compute centroid: V_mean = (V_A + V_B + ... + V_N) / N
    │
    ▼
L2-normalize centroid (required for IndexFlatIP cosine similarity)
    │
    ▼
FAISS nearest-neighbor search on centroid vector
    │
    ▼
Genre Jaccard re-ranking against combined genre footprint of all input films
    │
    ▼
Quality filters + sort → top 50 results
```

The pool state persists in localStorage across sessions. Slots can be edited or removed individually. No new index or data is required — the endpoint reads vectors directly from the already-loaded FAISS index via `index.reconstruct()`.


## Features

- **Semantic search** — understands thematic similarity, not just surface genre tags
- **Pool Mode** — select up to 5 movies and find recommendations at the geometric centroid of their embedding vectors; describe your taste as a combination rather than a single anchor
- **TMDB live integration** — real-time poster, rating, cast, trailer, and metadata on every card and detail page
- **Genre Jaccard boost** — validated 2.8pp improvement in domain relevance
- **Quality filters** — eliminates shorts, unrated obscurities, TV movies, documentaries
- **Three sort modes** — Similarity, Quality (vote-weighted), Strict Genre Match
- **TMDB API toggle** — compare our FAISS results against TMDB's own recommendation engine live
- **Fuzzy fallback** — "Did you mean?" suggestions when a title isn't in the index
- **Detail pages** — full cast, crew, trailer embed, keywords, budget/box office, tagline
- **Adult content handling** — 18+ badge instead of poster, carried through all surfaces
- **Daily auto-update** — GitHub Actions workflow rebuilds the index nightly from TMDB's Discover API


## Performance

Benchmarked on a hand-curated golden dataset of 100 anchor movies (20 franchise pairs, 20 cross-genre semantic pairs, 25 hard cases, 35 Bollywood/regional films).

| Model | Recall@5 | Recall@10 | nDCG@5 | nDCG@10 | MRR@5 | MRR@10 | TMDB Overlap@10 | Latency |
|---|---|---|---|---|---|---|---|---|
| **MiniLM** *(production)* | 16.3% | 20.0% | **0.277** | **0.279** | **0.262** | **0.266** | 1.12 | **1.64 ms** |
| MPNet | 16.4% | 20.5% | 0.253 | 0.277 | 0.238 | 0.251 | 1.12 | 10.38 ms |

The models are nearly identical on Recall — MPNet edges ahead by just 0.8pp on Recall@5 and 2.7pp on Recall@10. But MiniLM actually **beats MPNet on ranking quality**: higher nDCG@5 (0.277 vs 0.253) and MRR@5 (0.262 vs 0.238), meaning it surfaces relevant results higher up the list. At a **533% latency penalty** (~6.3× slower) for MPNet, the choice is clear: MiniLM wins on both speed and ranking quality.

> Recall numbers look modest by design. The evaluation deliberately targets **hard semantic pairs** — not obvious franchise sequels or genre clones. A system that finds *Burning* for *Parasite* and *Force Majeure* for *A Separation* is doing real work.


## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/your-username/movierec
cd movierec
pip install -r requirements.txt

# 2. Set your TMDB API key
echo "TMDB_API_KEY=your_key_here" > .env

# 3. Build the FAISS index (first run — ~30 min on CPU)
python build_index.py --model minilm --output-dir models/minilm

# 4. Start the server
python app.py
```

Visit `http://localhost:5000` — search for any movie, click it, and watch the recommendations load.


## Keeping the Index Fresh

### One-command local update (Windows)
```bat
auto_sync.bat
```
Fetches the latest movies from TMDB's Discover API, merges them into the dataset, and incrementally updates the FAISS index without a full rebuild.

### Automated nightly update (GitHub Actions)
The included `.github/workflows/daily_update.yml` runs at midnight UTC, rebuilds the MiniLM index from scratch, and uploads `faiss.index` + `index_data.pkl` to a Hugging Face dataset. The app downloads them on cold start if they're not present locally.

To enable:
1. Add `TMDB_API_KEY` and `HF_TOKEN` to your repository secrets
2. Set `repo_id` in the workflow to your Hugging Face dataset
3. Set `HF_INDEX_DATASET` in your deployment environment


## Project Structure

```
movierec/
├── app.py                  # Flask app — /smart_recommend, /recommend_multi, /enrich_tmdb_results, etc.
├── build_index.py          # Build FAISS index from scratch (MiniLM or MPNet)
├── update_index.py         # Incremental index update (new movies only)
├── smart_tmdb_fetcher.py   # TMDB Discover API fetcher + dataset merger
├── data_loader.py          # Load FAISS index + DataFrame from disk
├── data_utils.py           # Kaggle dataset path resolution
│
├── models/
│   └── minilm/
│       ├── faiss.index     # Vector index (Git LFS / download on cold start)
│       └── index_data.pkl  # DataFrame + title→index map (Git LFS)
│
├── static/
│   ├── script.js           # Frontend logic (Search mode, Pool mode, TMDB live)
│   ├── style.css           # All styles — index, pool UI, modal, detail page
│   └── icons/              # SVGs (search, fallback poster, 18+ badge)
│
├── templates/
│   ├── index.html          # Main page — Search/Pool toggle, modal, results grid
│   └── movie_detail.html   # Full movie detail page
│
├── bench_relevancy.py      # Ground-truth Recall/MRR/nDCG benchmark
├── bench_jaccard.py        # Genre boost ablation study
├── bench_tmdb_overlap.py   # TMDB overlap reference benchmark
├── bench_latency.py        # MiniLM vs MPNet inference latency benchmark
├── get_metrics.py          # Clean metrics summary for both models
│
├── golden_dataset.json     # 100-anchor hand-curated evaluation set
├── EVALUATION.md           # Full evaluation methodology and results
│
├── .github/workflows/
│   ├── daily_update.yml    # Nightly FAISS index rebuild + HF dataset upload
│   └── update_index.yml    # Weekly incremental index update + HF Spaces push
│
├── Dockerfile              # Container deployment (Hugging Face Spaces / self-hosted)
├── requirements.txt
└── auto_sync.bat           # One-click local update (Windows)
```


## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TMDB_API_KEY` | ✅ | TMDB v3 API key — get one free at [themoviedb.org](https://www.themoviedb.org/settings/api) |
| `HF_INDEX_DATASET` | Optional | Hugging Face dataset ID for remote index storage (e.g. `your-username/movie-rec-data`) |
| `MODEL_PATH` | Optional | Override model directory (default: `models/minilm`) |
| `TMDB_API_BASE` | Optional | Override TMDB API host (useful in regions that block `api.themoviedb.org`) |


## Evaluation

The evaluation framework is documented in full in [`EVALUATION.md`](EVALUATION.md). The short version:

- **Golden dataset**: 100 hand-curated anchor→ground-truth pairs across four difficulty tiers
- **Metrics**: Recall@5, Recall@10, nDCG@10, MRR@10 — all computed on raw FAISS cosine similarity with no boosts
- **Ablation**: Genre Jaccard boost validated independently on the full 100-anchor set
- **TMDB overlap**: Measured as a reference baseline — agreement with TMDB is not an optimization target

Ground truth pairs were selected *before* running any benchmarks to prevent label leakage.

To run the benchmarks yourself:

```bash
# Semantic quality (Recall, MRR, nDCG)
python bench_relevancy.py

# Genre boost ablation
python bench_jaccard.py --golden-file golden_dataset.json

# TMDB overlap comparison
python bench_tmdb_overlap.py

# Latency (MiniLM vs MPNet)
python bench_latency.py

# Clean summary table for both models
python get_metrics.py
```


## Docker

```bash
docker build -t movierec .
docker run -p 5000:5000 -e TMDB_API_KEY=your_key movierec
```


## Known Limitations

- Recall numbers are computed against one annotator's judgment. Production-grade evaluation would use multiple annotators with inter-rater agreement (Cohen's Kappa).
- The index covers ~90k movies filtered from the TMDB dataset. Very obscure or very new films may not be present — the app falls back to TMDB's own recommendation API in that case.
- Keyword and genre data quality varies in the source dataset; some older or non-English films have sparse metadata, which hurts semantic retrieval quality.
- The 20 franchise anchor pairs in the golden dataset are intentional sanity checks and should be excluded from aggregate semantic metrics when reporting real-world performance.


## Tech Stack

| Layer | Technology |
|---|---|
| Embeddings | `sentence-transformers` (MiniLM-L6-v2) |
| Vector search | `faiss-cpu` (IndexFlatIP — exact inner product) |
| Pool Mode | Centroid of selected movie vectors, L2-normalized, queried against same FAISS index |
| Backend | Flask |
| Data | TMDB Discover API + Kaggle TMDB dataset (930k movies) |
| Frontend | Vanilla JS + CSS — no framework |
| Metadata | TMDB API v3 (live, client-side) |
| Index hosting | Hugging Face Datasets (downloaded on cold start) |
| App hosting | Hugging Face Spaces (Docker) |
| CI/CD | GitHub Actions — nightly index rebuild + weekly HF Spaces push |


## Deployment

The live demo runs on Hugging Face Spaces via Docker. The `update_index.yml` workflow pushes to Spaces automatically on a weekly schedule via `git push huggingface main --force`.


## License

MIT