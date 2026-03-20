"""
TMDB Overlap Benchmark: Measures alignment between our FAISS recommendations
and TMDB's own recommendation API (https://api.themoviedb.org/3/movie/{id}/recommendations).

NOTE: TMDB is a reference baseline, not ground truth — do not optimize toward it.

Metrics per anchor:
  - Overlap@10 : size of intersection between FAISS top-10 and TMDB top-10
  - Jaccard@10 : |intersection| / |union| for the two top-10 sets

Usage:
  python bench_tmdb_overlap.py
  python bench_tmdb_overlap.py --model-path models/mpnet
  python bench_tmdb_overlap.py --golden-file golden_dataset.json
"""

import json
import os
import re
import sys
import time
import unicodedata

import faiss                  # noqa: F401 – imported via get_data()
import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

from data_loader import get_data

# ── stdout encoding (Windows Unicode safety) ──────────────────────────────────
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Load environment & API key ────────────────────────────────────────────────
load_dotenv(os.path.join(BASE_DIR, ".env"))
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not TMDB_API_KEY:
    print("❌  TMDB_API_KEY not found in .env — cannot run TMDB overlap benchmark.")
    sys.exit(1)

# Allow overriding the TMDB API host (some regions block api.themoviedb.org).
# Examples:
#   TMDB_API_BASE=https://api.tmdb.org/3
#   TMDB_API_BASE=https://api.themoviedb.org/3
TMDB_API_BASE = os.getenv("TMDB_API_BASE", "https://api.tmdb.org/3").rstrip("/")
TMDB_SEARCH_URL = f"{TMDB_API_BASE}/search/movie"
TMDB_RECS_URL   = f"{TMDB_API_BASE}/movie/{{id}}/recommendations"
RATE_LIMIT_SLEEP = 0.25   # seconds between TMDB API calls
TOP_K = 10


# ── Helpers ───────────────────────────────────────────────────────────────────
def normalize_title(title: str) -> str:
    """Case-, accent-, punctuation-insensitive normalization (mirrors bench_relevancy.py)."""
    if not isinstance(title, str):
        return ""
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def tmdb_search(title: str, year: int = None) -> int | None:
    """
    Resolve a movie title to its TMDB ID.
    - If year is provided, try a year-scoped search first.
    - Validate the result by comparing normalized titles before accepting.
    - Falls back to unscoped search if year-scoped returns nothing.
    - Returns None (and refuses to guess) if no confident match is found.
    """
    norm_query = normalize_title(title)

    def _search(params: dict) -> int | None:
        try:
            resp = requests.get(TMDB_SEARCH_URL, params=params, timeout=10)
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception as e:
            print(f"     [WARN] TMDB search failed for '{title}': {e}")
            return None

        # Check top 3 results for a normalized title match
        for r in results[:3]:
            if normalize_title(r.get("title", "")) == norm_query:
                return r["id"]
        return None

    # Pass 1: year-scoped (most reliable for ambiguous titles)
    if year:
        params = {
            "api_key": TMDB_API_KEY,
            "query": title,
            "language": "en-US",
            "page": 1,
            "primary_release_year": year,
        }
        result = _search(params)
        if result is not None:
            return result

    # Pass 2: unscoped fallback (for titles where year metadata is slightly off)
    params = {
        "api_key": TMDB_API_KEY,
        "query": title,
        "language": "en-US",
        "page": 1,
    }
    result = _search(params)
    if result is not None:
        return result

    # Refuse to guess — returning None causes the anchor to be logged as skipped
    # rather than silently corrupting metrics with a wrong-movie ID.
    print(f"     [WARN] No confident TMDB match found for '{title}' (year={year}). Skipping.")
    return None


def tmdb_recommendations(tmdb_id: int) -> list[str]:
    """Fetch TMDB top-10 recommendations for a given TMDB movie ID."""
    url = TMDB_RECS_URL.format(id=tmdb_id)
    params = {"api_key": TMDB_API_KEY, "language": "en-US", "page": 1}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return [r["title"] for r in results[:TOP_K] if r.get("title")]
    except Exception as e:
        print(f"     [WARN] TMDB recs fetch failed for id={tmdb_id}: {e}")
        return []


def quality_filter(movie: pd.Series) -> bool:
    """Same quality filters used in bench_relevancy.py / app.py."""
    runtime = float(movie.get("runtime", 0)) if pd.notna(movie.get("runtime")) else 0
    if 0 < runtime <= 40:
        return False

    vote_avg = float(movie.get("vote_average", 0)) if pd.notna(movie.get("vote_average")) else 0
    vote_cnt = float(movie.get("vote_count", 0)) if pd.notna(movie.get("vote_count")) else 0
    if vote_avg >= 10 or vote_avg == 0 or vote_cnt < 5:
        return False

    pop = float(movie.get("popularity", 0)) if pd.notna(movie.get("popularity")) else 0
    if pop <= 1.75:
        return False

    genres_str = str(movie.get("genres", "")) if pd.notna(movie.get("genres")) else ""
    if any(g in genres_str.lower() for g in ["tv movie", "documentary"]):
        return False

    return True


def faiss_top_k(anchor_idx: int, df: pd.DataFrame, index, k: int = TOP_K) -> list[str]:
    """Return top-k FAISS recommendations for the given anchor (no Jaccard boost, quality filtered)."""
    query_vector = index.reconstruct(int(anchor_idx)).reshape(1, -1)
    pool_size = k * 5
    _, I = index.search(query_vector, pool_size)

    results = []
    for i_idx in I[0]:
        if i_idx == anchor_idx or i_idx >= len(df):
            continue
        movie = df.iloc[i_idx]
        if not quality_filter(movie):
            continue
        results.append(movie.get("title", ""))
        if len(results) >= k:
            break
    return results


# ── Load FAISS index ───────────────────────────────────────────────────────────
import argparse

parser = argparse.ArgumentParser(description="TMDB Overlap Benchmark")
parser.add_argument("--model-path", default="models/minilm",
                    help="Path to model directory containing faiss.index and index_data.pkl.")
parser.add_argument("--golden-file", default="golden_dataset.json",
                    help="Path to golden dataset JSON.")
args = parser.parse_args()

model_path_arg = args.model_path
full_model_path = model_path_arg if os.path.isabs(model_path_arg) else os.path.join(BASE_DIR, model_path_arg)

if not os.path.exists(os.path.join(full_model_path, "faiss.index")):
    print(f"❌  No index found at {model_path_arg}/")
    print(f"   Run: python build_index.py --model minilm --output-dir {model_path_arg}")
    sys.exit(1)

print(f"📦 Loading index from {model_path_arg}/...")
df, title_to_index, index = get_data(model_path=model_path_arg)

titles_original = df["title"].fillna("").tolist()
titles_norm     = [normalize_title(t) for t in titles_original]
norm_to_idx     = {t: i for i, t in enumerate(titles_norm) if t}

# ID-based lookup if dataset has 'id' column
if "id" in df.columns:
    id_to_idx: dict[int, int] = {}
    for pos, raw_id in df["id"].items():
        if pd.isna(raw_id):
            continue
        try:
            id_to_idx[int(raw_id)] = pos
        except (TypeError, ValueError):
            pass
else:
    id_to_idx = {}

# ── Load golden dataset ────────────────────────────────────────────────────────
golden_file = args.golden_file
if not os.path.isabs(golden_file):
    golden_file = os.path.join(BASE_DIR, golden_file)

with open(golden_file, "r", encoding="utf-8") as f:
    golden_raw = json.load(f)

print(f"📋 Loaded {len(golden_raw)} anchors from {os.path.basename(golden_file)}\n")
print("=" * 70)
print("  TMDB OVERLAP BENCHMARK")
print("=" * 70)
print("  ⚠️  TMDB is a reference baseline, not ground truth — do not optimize toward it.")
print("=" * 70 + "\n")

# ── Main loop ─────────────────────────────────────────────────────────────────
per_anchor_overlaps: list[float] = []
per_anchor_jaccards: list[float] = []
skipped: list[str] = []

for entry in golden_raw:
    anchor_title = entry.get("anchor", "") if isinstance(entry, dict) else ""
    if not anchor_title:
        continue

    # 1. Resolve anchor in local FAISS index
    anchor_idx = None

    # Try TMDB ID first (if present in golden dataset)
    anchor_tmdb_id = entry.get("anchor_tmdb_id") if isinstance(entry, dict) else None
    if anchor_tmdb_id is not None and id_to_idx:
        try:
            anchor_idx = id_to_idx.get(int(anchor_tmdb_id))
        except (TypeError, ValueError):
            pass

    if anchor_idx is None:
        anchor_idx = norm_to_idx.get(normalize_title(anchor_title))

    if anchor_idx is None:
        print(f"  ⚠️  '{anchor_title}' — not in local index, skipping.")
        skipped.append(anchor_title)
        continue

    # 2. Resolve TMDB ID via search API (with year hint if available)
    time.sleep(RATE_LIMIT_SLEEP)
    anchor_year = entry.get("anchor_year") if isinstance(entry, dict) else None
    tmdb_id = tmdb_search(anchor_title, year=anchor_year)
    if tmdb_id is None:
        year_str = f" ({anchor_year})" if anchor_year else ""
        print(f"  ⚠️  '{anchor_title}'{year_str} — no confident TMDB match found, skipping.")
        skipped.append(anchor_title)
        continue

    # 3. Fetch TMDB recommendations
    time.sleep(RATE_LIMIT_SLEEP)
    tmdb_recs = tmdb_recommendations(tmdb_id)
    if not tmdb_recs:
        print(f"  ⚠️  '{anchor_title}' — TMDB returned 0 recommendations, skipping.")
        skipped.append(anchor_title)
        continue

    # 4. Fetch FAISS recommendations
    faiss_recs = faiss_top_k(anchor_idx, df, index)

    # 5. Compute metrics (normalize both sets for comparison)
    faiss_norm_set = {normalize_title(t) for t in faiss_recs}
    tmdb_norm_set  = {normalize_title(t) for t in tmdb_recs}

    intersection = faiss_norm_set & tmdb_norm_set
    union        = faiss_norm_set | tmdb_norm_set

    overlap  = float(len(intersection))
    jaccard  = overlap / len(union) if union else 0.0

    per_anchor_overlaps.append(overlap)
    per_anchor_jaccards.append(jaccard)

    print(f"  🎬 {anchor_title}")
    print(f"     FAISS Top-10  : {faiss_recs[:5]}{'...' if len(faiss_recs) > 5 else ''}")
    print(f"     TMDB  Top-10  : {tmdb_recs[:5]}{'...' if len(tmdb_recs) > 5 else ''}")
    print(f"     Overlap@10    : {overlap:.0f}  |  Jaccard@10: {jaccard:.3f}\n")

# ── Final summary ──────────────────────────────────────────────────────────────
print("=" * 70)
print("  FINAL AVERAGES")
print("=" * 70)
evaluated = len(per_anchor_overlaps)
avg_overlap = float(np.mean(per_anchor_overlaps)) if per_anchor_overlaps else 0.0
avg_jaccard = float(np.mean(per_anchor_jaccards)) if per_anchor_jaccards else 0.0
print(f"  Anchors evaluated  : {evaluated} / {len(golden_raw)}")
print(f"  Avg Overlap@10     : {avg_overlap:.2f}")
print(f"  Avg Jaccard@10     : {avg_jaccard:.3f}")

if skipped:
    print(f"\n  ⛔ Skipped ({len(skipped)} anchors):")
    for s in skipped:
        print(f"     - {s}")

print("\n  NOTE: TMDB is a reference baseline, not ground truth — do not optimize toward it.")
print("=" * 70)
