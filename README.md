# Movie Recommendation System

A semantic movie recommendation engine using FAISS and sentence transformers.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

## Environment Variables

Create a `.env` file with:
```
TMDB_API_KEY=your_tmdb_api_key_here
```

## Features

- Semantic similarity search using MiniLM embeddings
- 25% genre Jaccard boost for domain relevance
- Quality filters (removes TV movies, documentaries, low-vote films)
- TMDB integration for posters and metadata

## Performance

- **Latency:** ~1.64 ms/query using MiniLM
- **Domain Relevance:** 98.7% genre alignment achieved via Jaccard boost
- **Retrieval:** Thoroughly evaluated on semantic relevance, see `EVALUATION.md` for full metrics.

## Project Structure

- `app.py` - Flask web application
- `build_index.py` - Build FAISS index from dataset
- `bench_*.py` - Benchmarking scripts
- `data_loader.py` - Data loading utilities