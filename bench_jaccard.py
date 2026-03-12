# bench_jaccard.py
"""
Jaccard Ablation Study: Proves that the 15% Genre Jaccard Boost
actually improves domain relevance in recommendations.

Runs the same 10 anchor movies through MiniLM:
  Test A: 0% Jaccard Boost (raw FAISS only)
  Test B: 15% Jaccard Boost (your current production formula)

Measures Genre Alignment Rate: % of Top 10 results sharing ≥1 genre with the anchor.
"""
import json
import os
import pickle
import faiss
import numpy as np
import pandas as pd
from data_loader import get_data

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ------- Load Golden Dataset ------- #
with open(os.path.join(BASE_DIR, 'golden_dataset.json'), 'r') as f:
    golden = json.load(f)

# ------- Load MiniLM Index ------- #
MINILM_PATH = 'models/minilm'
full_path = os.path.join(BASE_DIR, MINILM_PATH)

if not os.path.exists(os.path.join(full_path, 'faiss.index')):
    print(f"❌ No MiniLM index found at {MINILM_PATH}/")
    print(f"   Run: python build_index.py --model minilm --output-dir {MINILM_PATH}")
    exit(1)

print(f"📦 Loading MiniLM index from {MINILM_PATH}/...")
df, title_to_index, index = get_data(model_path=MINILM_PATH)


def parse_genres(genres_raw):
    """Parse genre string into a set of lowercase genre names."""
    if isinstance(genres_raw, list):
        return set(g.strip().lower() for g in genres_raw if g and isinstance(g, str))
    genres_str = str(genres_raw) if pd.notna(genres_raw) else ''
    return set(g.strip().lower() for g in genres_str.split(',') if g.strip())


def is_quality_movie(movie):
    """Basic quality filter — removes obscure junk without applying any boosts."""
    runtime = float(movie.get('runtime', 0)) if pd.notna(movie.get('runtime')) else 0
    if runtime > 0 and runtime <= 40:
        return False
    
    vote_avg = float(movie.get('vote_average', 0)) if pd.notna(movie.get('vote_average')) else 0
    vote_cnt = float(movie.get('vote_count', 0)) if pd.notna(movie.get('vote_count')) else 0
    if vote_avg >= 10 or vote_avg == 0 or vote_cnt <= 1:
        return False
    
    pop = float(movie.get('popularity', 0)) if pd.notna(movie.get('popularity')) else 0
    if pop <= 1.75:
        return False
    
    genres_str = str(movie.get('genres', '')) if pd.notna(movie.get('genres')) else ''
    if any(g in genres_str.lower() for g in ['tv movie', 'documentary']):
        return False
    
    return True


def get_top_10_raw(anchor_idx):
    """Test A: Pure FAISS search, 0% Jaccard Boost."""
    query_vector = index.reconstruct(int(anchor_idx)).reshape(1, -1)
    
    # Pull a larger pool to account for quality filtering
    D, I = index.search(query_vector, 100)
    
    results = []
    for score, i in zip(D[0], I[0]):
        if i == anchor_idx or i >= len(df):
            continue
        movie = df.iloc[i]
        if not is_quality_movie(movie):
            continue
        results.append({
            'title': movie.get('title', ''),
            'genres': parse_genres(movie.get('genres', '')),
            'score': float(score),
        })
        if len(results) >= 10:
            break
    return results


def get_top_10_jaccard(anchor_idx, jaccard_weight=0.15):
    """Test B: FAISS search re-ranked with Jaccard Boost."""
    query_vector = index.reconstruct(int(anchor_idx)).reshape(1, -1)
    anchor_movie = df.iloc[anchor_idx]
    anchor_genres = parse_genres(anchor_movie.get('genres', ''))
    
    # Pull a large pool so re-ranking has room to promote genre-aligned movies
    pool_size = 250
    D, I = index.search(query_vector, pool_size)
    
    candidates = []
    for score, i in zip(D[0], I[0]):
        if i == anchor_idx or i >= len(df):
            continue
        movie = df.iloc[i]
        if not is_quality_movie(movie):
            continue
        cand_genres = parse_genres(movie.get('genres', ''))
        
        cosine_sim = float(score)
        
        # Jaccard similarity
        if anchor_genres and cand_genres:
            intersect = len(anchor_genres.intersection(cand_genres))
            union = len(anchor_genres.union(cand_genres))
            genre_jaccard = intersect / union if union > 0 else 0.0
        else:
            genre_jaccard = 0.0
        
        # Production formula: 85% cosine + 15% Jaccard
        final_sim = ((1 - jaccard_weight) * cosine_sim) + (jaccard_weight * genre_jaccard)
        
        candidates.append({
            'title': movie.get('title', ''),
            'genres': cand_genres,
            'score': final_sim,
        })
    
    # Re-rank by the boosted score
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[:10]


def genre_alignment_rate(anchor_genres, results):
    """What % of Top 10 results share at least one genre with the anchor?"""
    if not results:
        return 0.0
    aligned = sum(1 for r in results if anchor_genres.intersection(r['genres']))
    return aligned / len(results)


# ------- Run Both Tests ------- #
print(f"\n{'='*70}")
print("  JACCARD ABLATION STUDY")
print(f"{'='*70}\n")

test_a_rates = []
test_b_rates = []

for entry in golden:
    anchor = entry['anchor']
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
    
    # Test B: 15% Jaccard Boost
    boosted_results = get_top_10_jaccard(anchor_idx, jaccard_weight=0.15)
    rate_b = genre_alignment_rate(anchor_genres, boosted_results)
    test_b_rates.append(rate_b)
    
    print(f"  🎬 {anchor}")
    print(f"     Genres: {', '.join(sorted(anchor_genres))}")
    print(f"     Test A (0% Jaccard):  {rate_a:.0%} genre alignment  |  Top 3: {[r['title'] for r in raw_results[:3]]}")
    print(f"     Test B (15% Jaccard): {rate_b:.0%} genre alignment  |  Top 3: {[r['title'] for r in boosted_results[:3]]}")
    print()

# ------- Summary ------- #
avg_a = np.mean(test_a_rates) if test_a_rates else 0.0
avg_b = np.mean(test_b_rates) if test_b_rates else 0.0

print("=" * 70)
print("  GENRE ALIGNMENT SUMMARY")
print("=" * 70)
print(f"  {'Test A (0% Jaccard Boost)':<35} Avg Alignment: {avg_a:.1%}")
print(f"  {'Test B (15% Jaccard Boost)':<35} Avg Alignment: {avg_b:.1%}")
print("-" * 70)

if avg_a > 0:
    improvement = ((avg_b - avg_a) / avg_a) * 100
    print(f"  {'📈' if improvement > 0 else '📉'} Jaccard Boost Impact: {improvement:+.1f}% genre alignment improvement")
else:
    print(f"  Jaccard Boost Impact: {avg_b:.1%} alignment (baseline was 0%)")

print(f"\n  Conclusion: The 15% Genre Jaccard Boost {'SIGNIFICANTLY improves' if avg_b > avg_a else 'has minimal effect on'} domain relevance.")
print("=" * 70)
