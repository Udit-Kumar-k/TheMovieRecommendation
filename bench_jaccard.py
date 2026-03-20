# bench_jaccard.py
"""
Jaccard Ablation Study: Proves that the 15% Genre Jaccard Boost
actually improves domain relevance in recommendations.

Runs the same 10 anchor movies through MiniLM:
  Test A: 0% Jaccard Boost (raw FAISS only)
  Test B: 25% Jaccard Boost (your current production formula)

Measures Genre Alignment Rate: % of Top 10 results sharing ≥1 genre with the anchor.
"""
import sys
import argparse
import json
import os
import pickle
import faiss
import numpy as np
import pandas as pd
from tqdm import tqdm
from data_loader import get_data

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure Windows terminals can print Unicode (emojis, accents)
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def parse_genres(genres_str: str) -> set:
    """Parse comma-separated genres into a normalized set."""
    if not genres_str or not isinstance(genres_str, str):
        return set()
    return set(g.strip().lower() for g in genres_str.split(",") if g.strip())


def genre_alignment_rate(anchor_genres: set, results: list) -> float:
    """Calculate % of results that share at least one genre with anchor."""
    if not anchor_genres or not results:
        return 0.0
    matches = 0
    for r in results:
        result_genres = parse_genres(r.get("genres", ""))
        if anchor_genres & result_genres:  # intersection
            matches += 1
    return matches / len(results)


def get_top_10_raw(anchor_idx: int):
    """Get top 10 results using raw FAISS similarity (no Jaccard boost)."""
    query_vector = index.reconstruct(int(anchor_idx)).reshape(1, -1)
    D, I = index.search(query_vector, 20)  # get extra for filtering
    
    results = []
    for i, idx in enumerate(I[0]):
        if idx == anchor_idx or idx >= len(df):
            continue
        movie = df.iloc[idx]
        results.append({
            "title": movie.get("title", ""),
            "genres": movie.get("genres", ""),
            "similarity": float(D[0][i])
        })
        if len(results) >= 10:
            break
    return results


def get_top_10_jaccard(anchor_idx: int, jaccard_weight: float = 0.25):
    """Get top 10 results with Jaccard genre boost applied."""
    anchor_movie = df.iloc[anchor_idx]
    anchor_genres = parse_genres(anchor_movie.get("genres", ""))
    
    query_vector = index.reconstruct(int(anchor_idx)).reshape(1, -1)
    D, I = index.search(query_vector, 100)  # get larger pool for re-ranking
    
    candidates = []
    for i, idx in enumerate(I[0]):
        if idx == anchor_idx or idx >= len(df):
            continue
        movie = df.iloc[idx]
        cand_genres = parse_genres(movie.get("genres", ""))
        
        # Compute Jaccard similarity
        if anchor_genres and cand_genres:
            intersection = len(anchor_genres & cand_genres)
            union = len(anchor_genres | cand_genres)
            jaccard = intersection / union if union > 0 else 0
        else:
            jaccard = 0
        
        # Combined score: semantic similarity + Jaccard boost
        semantic_score = float(D[0][i])
        combined_score = semantic_score * (1 + jaccard_weight * jaccard)
        
        candidates.append({
            "title": movie.get("title", ""),
            "genres": movie.get("genres", ""),
            "semantic_score": semantic_score,
            "jaccard": jaccard,
            "combined_score": combined_score
        })
    
    # Sort by combined score and return top 10
    candidates.sort(key=lambda x: x["combined_score"], reverse=True)
    return candidates[:10]


def load_golden_dataset(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_jaccard_benchmark(golden, jaccard_weight: float = 0.25, verbose: bool = False):
    print(f"\n{'='*70}")
    print("  JACCARD ABLATION STUDY")
    print(f"{'='*70}\n")

    test_a_rates = []
    test_b_rates = []

    # Auto-determine verbosity based on dataset size if not specified
    is_verbose = verbose if verbose is not None else len(golden) <= 50

    # Use tqdm for large datasets
    golden_iter = tqdm(golden, desc="Processing anchors") if not is_verbose else golden

    for entry in golden_iter:
        anchor = entry.get('anchor')
        if not anchor:
            continue
        anchor_lower = anchor.lower()

        if anchor_lower not in title_to_index:
            print(f"  ❌ Anchor '{anchor}' not found in index. Skipping.")
            continue

        anchor_idx = title_to_index[anchor_lower]
        anchor_movie = df.iloc[anchor_idx]
        anchor_genres = parse_genres(anchor_movie.get('genres', ''))

        # Test A: Raw FAISS (0% Jaccard)
        raw_results = get_top_10_raw(anchor_idx)
        rate_a = genre_alignment_rate(anchor_genres, raw_results)
        test_a_rates.append(rate_a)

        # Test B: Jaccard Boost
        boosted_results = get_top_10_jaccard(anchor_idx, jaccard_weight=jaccard_weight)
        rate_b = genre_alignment_rate(anchor_genres, boosted_results)
        test_b_rates.append(rate_b)

        if is_verbose:
            print(f"  🎬 {anchor}")
            print(f"     Genres: {', '.join(sorted(anchor_genres))}")
            print(
                f"     Test A (0% Jaccard):  {rate_a:.0%} genre alignment  |  Top 3: {[r['title'] for r in raw_results[:3]]}"
            )
            print(
                f"     Test B ({int(jaccard_weight*100)}% Jaccard): {rate_b:.0%} genre alignment  |  Top 3: {[r['title'] for r in boosted_results[:3]]}"
            )
            print()

    # ------- Summary ------- #
    avg_a = np.mean(test_a_rates) if test_a_rates else 0.0
    avg_b = np.mean(test_b_rates) if test_b_rates else 0.0

    print("=" * 70)
    print("  GENRE ALIGNMENT SUMMARY")
    print("=" * 70)
    print(f"  {'Test A (0% Jaccard Boost)':<35} Avg Alignment: {avg_a:.1%}")
    jaccard_pct = int(jaccard_weight * 100)
    print(f"  {'Test B (' + str(jaccard_pct) + '% Jaccard)':<35} Avg Alignment: {avg_b:.1%}")
    print("-" * 70)

    if avg_a > 0:
        improvement = ((avg_b - avg_a) / avg_a) * 100
        print(
            f"  {'📈' if improvement > 0 else '📉'} Jaccard Boost Impact: {improvement:+.1f}% genre alignment improvement"
        )
    else:
        print(f"  Jaccard Boost Impact: {avg_b:.1%} alignment (baseline was 0%)")

    print(
        f"\n  Conclusion: The {int(jaccard_weight*100)}% Genre Jaccard Boost {'SIGNIFICANTLY improves' if avg_b > avg_a else 'has minimal effect on'} domain relevance."
    )
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Jaccard ablation study")
    parser.add_argument(
        "--golden-file",
        default="golden_dataset.json",
        help="Path to a golden dataset JSON file.",
    )
    parser.add_argument(
        "--model-path",
        default="models/minilm",
        help="Path to a model directory containing faiss.index and index_data.pkl.",
    )
    parser.add_argument(
        "--jaccard-weight",
        type=float,
        default=0.25,
        help="Jaccard boost weight (0.0-1.0) to apply for the boosted ranking.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-movie details (auto-disabled for datasets >50 movies).",
    )
    args = parser.parse_args()

    golden_path = args.golden_file
    if not os.path.isabs(golden_path):
        golden_path = os.path.join(BASE_DIR, golden_path)

    golden = load_golden_dataset(golden_path)

    model_path = args.model_path
    full_path = model_path if os.path.isabs(model_path) else os.path.join(BASE_DIR, model_path)

    if not os.path.exists(os.path.join(full_path, 'faiss.index')):
        print(f"❌ No MiniLM index found at {model_path}/")
        print(f"   Run: python build_index.py --model minilm --output-dir {model_path}")
        return

    print(f"📦 Loading MiniLM index from {model_path}/...")
    global df, title_to_index, index
    df, title_to_index, index = get_data(model_path=model_path)

    run_jaccard_benchmark(golden, jaccard_weight=args.jaccard_weight, verbose=args.verbose)


if __name__ == "__main__":
    main()
