"""
Ground Truth Recall Benchmark: Tests which embedding model has a "smarter brain"
by measuring Recall@K and ranking quality against a curated golden dataset.

Uses RAW FAISS cosine similarity — no Jaccard boost, no quality sorting.
Applies only basic quality filters (runtime, vote_count, etc.) to keep obscure garbage out.

This script supports:
- Robust title normalization (case-insensitive, accent-insensitive, punctuation-stripped)
- Optional TMDB IDs in the golden dataset for exact matching
- Graded relevance labels for each ground-truth item
- Recall@K, MRR@K, and nDCG@K metrics
"""

import json
import os
import pickle
import re
import unicodedata

import faiss
import numpy as np
import pandas as pd

from data_loader import get_data

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ------- Helpers ------- #
def normalize_title(title: str) -> str:
    """
    Normalize a title for robust matching:
    - Lowercase
    - Strip accents
    - Remove punctuation / non-alphanumerics
    - Collapse whitespace
    """
    if not isinstance(title, str):
        return ""
    # Strip accents
    text = unicodedata.normalize("NFKD", title)
    text = text.encode("ascii", "ignore").decode("ascii")
    # Lowercase and remove non-alphanumeric
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def dcg_at_k(relevances, k: int) -> float:
    """Compute Discounted Cumulative Gain at K."""
    dcg = 0.0
    for rank, rel in enumerate(relevances[:k], start=1):
        if rel <= 0:
            continue
        dcg += rel / np.log2(rank + 1)
    return dcg


def ndcg_at_k(relevances, k: int) -> float:
    """Compute Normalized DCG at K given a list of relevances in rank order."""
    dcg = dcg_at_k(relevances, k)
    # Ideal DCG: sort relevances by descending score
    sorted_rels = sorted(relevances, reverse=True)
    idcg = dcg_at_k(sorted_rels, k)
    if idcg == 0:
        return 0.0
    return dcg / idcg


# ------- Load Golden Dataset ------- #
with open(os.path.join(BASE_DIR, "golden_dataset.json"), "r", encoding="utf-8") as f:
    golden_raw = json.load(f)

print(f"📋 Loaded {len(golden_raw)} anchor movies from golden_dataset.json\n")

# Normalize golden dataset into a richer internal format:
# Each entry becomes:
# {
#   "anchor_title": str,
#   "anchor_tmdb_id": Optional[int],
#   "ground_truth": [
#       {
#           "title": str,
#           "tmdb_id": Optional[int],
#           "relevance": float   # default 1.0 if not provided
#       },
#       ...
#   ]
# }
golden = []
for entry in golden_raw:
    anchor_title = entry.get("anchor", "")
    anchor_tmdb_id = entry.get("anchor_tmdb_id")

    gt_list = entry.get("ground_truth", [])
    normalized_gt = []

    # Backwards compatible: list of plain titles
    if gt_list and isinstance(gt_list[0], str):
        for t in gt_list:
            normalized_gt.append(
                {
                    "title": t,
                    "tmdb_id": None,
                    "relevance": 1.0,
                }
            )
    else:
        # New-style format: list of objects with optional relevance and tmdb_id
        for gt in gt_list:
            if not isinstance(gt, dict):
                continue
            normalized_gt.append(
                {
                    "title": gt.get("title", ""),
                    "tmdb_id": gt.get("tmdb_id"),
                    "relevance": float(gt.get("relevance", 1.0)),
                }
            )

    golden.append(
        {
            "anchor_title": anchor_title,
            "anchor_tmdb_id": anchor_tmdb_id,
            "ground_truth": normalized_gt,
        }
    )

# ------- Config ------- #
RECALL_K_VALUES = [10, 50]  # Check both Top 10 and Top 50

# ------- Define Models ------- #
model_configs = [
    ("MiniLM", "models/minilm"),
    ("MPNet", "models/mpnet"),
]

all_results = {}

for model_name, model_path in model_configs:
    full_path = os.path.join(BASE_DIR, model_path)

    # Check if the index exists for this model
    if not os.path.exists(os.path.join(full_path, "faiss.index")):
        print(f"⚠️  Skipping {model_name} — no index found at {model_path}/")
        print(f"   Run: python build_index.py --model {model_name.lower()} --output-dir {model_path}\n")
        continue

    print(f"{'='*70}")
    print(f"  Testing: {model_name} ({model_path})")
    print(f"{'='*70}")

    df, title_to_index, index = get_data(model_path=model_path)

    # Build helper structures from the DataFrame
    titles_original = df["title"].fillna("").tolist()
    titles_norm = [normalize_title(t) for t in titles_original]

    # Title-based lookup (normalized)
    norm_title_to_index = {t: i for i, t in enumerate(titles_norm) if t}

    # ID-based lookup if available
    if "id" in df.columns:
        id_to_index = {}
        for idx, tmdb_id in df["id"].items():
            if pd.isna(tmdb_id):
                continue
            try:
                tmdb_id_int = int(tmdb_id)
            except (TypeError, ValueError):
                continue
            id_to_index[tmdb_id_int] = idx
    else:
        id_to_index = {}

    ids = df["id"].tolist() if "id" in df.columns else [None] * len(df)

    max_k = max(RECALL_K_VALUES)
    model_recalls = {k: [] for k in RECALL_K_VALUES}
    model_mrr = {k: [] for k in RECALL_K_VALUES}
    model_ndcg = {k: [] for k in RECALL_K_VALUES}

    for entry in golden:
        anchor_title = entry["anchor_title"]
        anchor_tmdb_id = entry.get("anchor_tmdb_id")
        gt_items = entry["ground_truth"]

        # Build ground-truth maps for this anchor
        gt_titles = [gt["title"] for gt in gt_items]
        gt_norm_titles = [normalize_title(t) for t in gt_titles]
        gt_title_to_rel = {
            normalize_title(gt["title"]): float(gt.get("relevance", 1.0))
            for gt in gt_items
        }
        gt_id_to_rel = {}
        for gt in gt_items:
            tmdb_id = gt.get("tmdb_id")
            if tmdb_id is None:
                continue
            try:
                tmdb_id_int = int(tmdb_id)
            except (TypeError, ValueError):
                continue
            gt_id_to_rel[tmdb_id_int] = float(gt.get("relevance", 1.0))

        # Find anchor index: prefer TMDB ID if provided, else normalized title
        anchor_idx = None
        if anchor_tmdb_id is not None and id_to_index:
            try:
                tmdb_anchor_id = int(anchor_tmdb_id)
                anchor_idx = id_to_index.get(tmdb_anchor_id)
            except (TypeError, ValueError):
                anchor_idx = None

        if anchor_idx is None:
            anchor_norm = normalize_title(anchor_title)
            anchor_idx = norm_title_to_index.get(anchor_norm)

        if anchor_idx is None:
            print(f"  ❌ Anchor '{anchor_title}' not found in {model_name} index. Skipping.")
            continue

        # Raw FAISS search — pure cosine similarity, no boosts
        # Pull a bigger pool so we still have enough after quality filtering
        query_vector = index.reconstruct(int(anchor_idx)).reshape(1, -1)
        search_pool = max_k * 5
        D, I = index.search(query_vector, search_pool)

        # Get top results (excluding anchor + filtering out obscure junk)
        top_indices = []
        for i_idx in I[0]:
            if i_idx == anchor_idx or i_idx >= len(df):
                continue

            movie = df.iloc[i_idx]

            # Quality filters — same logic as build_index/app.py
            runtime = float(movie.get("runtime", 0)) if pd.notna(movie.get("runtime")) else 0
            if 0 < runtime <= 40:
                continue

            vote_avg = float(movie.get("vote_average", 0)) if pd.notna(movie.get("vote_average")) else 0
            vote_cnt = float(movie.get("vote_count", 0)) if pd.notna(movie.get("vote_count")) else 0
            if vote_avg >= 10 or vote_avg == 0 or vote_cnt <= 1:
                continue

            pop = float(movie.get("popularity", 0)) if pd.notna(movie.get("popularity")) else 0
            if pop <= 1.75:
                continue

            genres_str = str(movie.get("genres", "")) if pd.notna(movie.get("genres")) else ""
            if any(g in genres_str.lower() for g in ["tv movie", "documentary"]):
                continue

            top_indices.append(i_idx)
            if len(top_indices) >= max_k:
                break

        # Build lists used for metrics and printing
        top_norm_titles = [titles_norm[i] for i in top_indices]
        top_display_titles = [titles_original[i] for i in top_indices]
        top_ids = [ids[i] for i in top_indices]

        print(f"\n  🎬 Anchor: {anchor_title}")
        print(f"     Ground Truth: {gt_titles}")

        # Per-K metrics
        for k in RECALL_K_VALUES:
            top_k_norm = top_norm_titles[:k]
            top_k_ids = top_ids[:k]

            # Recall@K (binary): treat any match (by ID or normalized title) as a hit
            hits_mask = []
            for idx_rank, (cand_norm, cand_id) in enumerate(zip(top_k_norm, top_k_ids)):
                is_hit = False
                if cand_id is not None and cand_id in gt_id_to_rel:
                    is_hit = True
                elif cand_norm in gt_norm_titles:
                    is_hit = True
                hits_mask.append(is_hit)

            num_hits = sum(hits_mask)
            recall = num_hits / max(len(gt_items), 1)
            model_recalls[k].append(recall)

            # MRR@K (binary relevance, first hit position)
            first_hit_rank = None
            for rank_idx, is_hit in enumerate(hits_mask, start=1):
                if is_hit:
                    first_hit_rank = rank_idx
                    break
            if first_hit_rank is not None:
                model_mrr[k].append(1.0 / first_hit_rank)
            else:
                model_mrr[k].append(0.0)

            # nDCG@K (graded relevance)
            rank_rels = []
            for cand_norm, cand_id in zip(top_k_norm, top_k_ids):
                rel = 0.0
                if cand_id is not None and cand_id in gt_id_to_rel:
                    rel = gt_id_to_rel[cand_id]
                else:
                    rel = gt_title_to_rel.get(cand_norm, 0.0)
                rank_rels.append(rel)

            ndcg = ndcg_at_k(rank_rels, k)
            model_ndcg[k].append(ndcg)

            if k == RECALL_K_VALUES[0]:
                # For human-readable summary, show which titles matched in the top-K
                hit_titles = []
                for cand_title, is_hit in zip(top_display_titles[:k], hits_mask):
                    if is_hit:
                        hit_titles.append(cand_title)

                print(
                    f"     Found in Top {k} ({num_hits}/{len(gt_items)}): "
                    f"{hit_titles if hit_titles else ['None']}"
                )

                missed_titles = []
                for gt_title in gt_titles:
                    gt_norm = normalize_title(gt_title)
                    found = False
                    for cand_norm, cand_id in zip(top_k_norm, top_k_ids):
                        if cand_id is not None and cand_id in gt_id_to_rel:
                            # If any ground-truth ID matches, we consider it covered
                            if gt_id_to_rel.get(cand_id, None) is not None:
                                found = True
                                break
                        if cand_norm == gt_norm:
                            found = True
                            break
                    if not found:
                        missed_titles.append(gt_title)

                print(f"     Missed:          {missed_titles if missed_titles else ['None']}")

        # Print all metrics on one line (for the last K)
        recall_str = " | ".join(
            [f"Recall@{k}: {model_recalls[k][-1]:.0%}" for k in RECALL_K_VALUES]
        )
        mrr_str = " | ".join(
            [f"MRR@{k}: {model_mrr[k][-1]:.2f}" for k in RECALL_K_VALUES]
        )
        ndcg_str = " | ".join(
            [f"nDCG@{k}: {model_ndcg[k][-1]:.2f}" for k in RECALL_K_VALUES]
        )
        print(f"     {recall_str}")
        print(f"     {mrr_str}")
        print(f"     {ndcg_str}")

    # Aggregate metrics for this model
    avg_recalls = {k: float(np.mean(v)) if v else 0.0 for k, v in model_recalls.items()}
    avg_mrr = {k: float(np.mean(v)) if v else 0.0 for k, v in model_mrr.items()}
    avg_ndcg = {k: float(np.mean(v)) if v else 0.0 for k, v in model_ndcg.items()}

    all_results[model_name] = {
        "recall": avg_recalls,
        "mrr": avg_mrr,
        "ndcg": avg_ndcg,
    }

    print(f"\n  📊 {model_name} Averages:")
    for k in RECALL_K_VALUES:
        print(
            f"     @ {k:>2}: "
            f"Recall={avg_recalls[k]:.1%}, "
            f"MRR={avg_mrr[k]:.3f}, "
            f"nDCG={avg_ndcg[k]:.3f}"
        )
    print()

# ------- Final Comparison ------- #
if len(all_results) == 2:
    print("\n" + "=" * 70)
    print("  MODEL COMPARISON: MiniLM vs MPNet")
    print("=" * 70)

    header = f"{'Model':<15}"
    for k in RECALL_K_VALUES:
        header += f"{('Recall@' + str(k)):<15}{('MRR@' + str(k)):<15}{('nDCG@' + str(k)):<15}"
    print("  " + header)
    print("-" * 70)

    for name, metrics in all_results.items():
        line = f"  {name:<15}"
        for k in RECALL_K_VALUES:
            line += (
                f"{metrics['recall'][k]:<15.1%}"
                f"{metrics['mrr'][k]:<15.3f}"
                f"{metrics['ndcg'][k]:<15.3f}"
            )
        print(line)

    print("-" * 70)
    minilm = all_results.get("MiniLM", {})
    mpnet = all_results.get("MPNet", {})

    for k in RECALL_K_VALUES:
        minilm_r = minilm.get("recall", {}).get(k, 0)
        mpnet_r = mpnet.get("recall", {}).get(k, 0)
        if minilm_r > 0:
            improvement = ((mpnet_r - minilm_r) / minilm_r) * 100
            print(f"  Recall@{k} Improvement (MPNet vs MiniLM): {improvement:+.1f}%")

    print("=" * 70)
elif len(all_results) == 1:
    print(
        "\n⚠️  Only one model index found. Build both indexes to see the comparison."
    )
