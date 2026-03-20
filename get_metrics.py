"""
Clean metrics extractor — runs precision/recall/nDCG/MRR for both models
and prints a clean summary table to stdout.
"""
import sys, os, json, pickle, re, unicodedata
import faiss, numpy as np, pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def normalize_title(title):
    if not isinstance(title, str):
        return ""
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def dcg_at_k(rels, k):
    return sum(r / np.log2(i + 2) for i, r in enumerate(rels[:k]) if r > 0)


def ndcg_at_k(rels, k):
    dcg = dcg_at_k(rels, k)
    idcg = dcg_at_k(sorted(rels, reverse=True), k)
    return dcg / idcg if idcg > 0 else 0.0


with open(os.path.join(BASE_DIR, "golden_dataset.json"), encoding="utf-8") as f:
    golden_raw = json.load(f)

golden = []
for entry in golden_raw:
    gt_list = entry.get("ground_truth", [])
    if gt_list and isinstance(gt_list[0], str):
        gts = [{"title": t, "tmdb_id": None, "relevance": 1.0} for t in gt_list]
    else:
        gts = [
            {
                "title": g.get("title", ""),
                "tmdb_id": g.get("tmdb_id"),
                "relevance": float(g.get("relevance", 1.0)),
            }
            for g in gt_list
            if isinstance(g, dict)
        ]
    golden.append(
        {
            "anchor_title": entry.get("anchor", ""),
            "anchor_tmdb_id": entry.get("anchor_tmdb_id"),
            "ground_truth": gts,
        }
    )

KS = [5, 10]
all_results = {}

for model_name, model_path in [("MiniLM", "models/minilm"), ("MPNet", "models/mpnet")]:
    full = os.path.join(BASE_DIR, model_path)
    if not os.path.exists(os.path.join(full, "faiss.index")):
        print(f"{model_name}: no index found, skipping.")
        continue

    with open(os.path.join(full, "index_data.pkl"), "rb") as f:
        d = pickle.load(f)
    df = d["df"]
    index = faiss.read_index(os.path.join(full, "faiss.index"))

    titles_norm = [normalize_title(t) for t in df["title"].fillna("")]
    norm_to_idx = {t: i for i, t in enumerate(titles_norm) if t}
    id_to_idx = {}
    if "id" in df.columns:
        for pos, rid in df["id"].items():
            try:
                id_to_idx[int(rid)] = pos
            except Exception:
                pass

    recalls = {k: [] for k in KS}
    mrrs = {k: [] for k in KS}
    ndcgs = {k: [] for k in KS}
    skipped = 0

    for entry in golden:
        anchor_idx = None
        if entry["anchor_tmdb_id"]:
            try:
                anchor_idx = id_to_idx.get(int(entry["anchor_tmdb_id"]))
            except Exception:
                pass
        if anchor_idx is None:
            anchor_idx = norm_to_idx.get(normalize_title(entry["anchor_title"]))
        if anchor_idx is None:
            skipped += 1
            continue

        gts = entry["ground_truth"]
        gt_norm = {normalize_title(g["title"]) for g in gts}
        gt_id = {}
        for g in gts:
            if g["tmdb_id"] is not None:
                try:
                    gt_id[int(g["tmdb_id"])] = g["relevance"]
                except Exception:
                    pass
        gt_norm_rel = {normalize_title(g["title"]): g["relevance"] for g in gts}

        qv = index.reconstruct(int(anchor_idx)).reshape(1, -1)
        _, I = index.search(qv, max(KS) * 5)

        top = []
        for i in I[0]:
            if i == anchor_idx or i >= len(df):
                continue
            m = df.iloc[i]
            rt = float(m.get("runtime", 0)) if pd.notna(m.get("runtime")) else 0
            if 0 < rt <= 40:
                continue
            va = float(m.get("vote_average", 0)) if pd.notna(m.get("vote_average")) else 0
            vc = float(m.get("vote_count", 0)) if pd.notna(m.get("vote_count")) else 0
            if va >= 10 or va == 0 or vc < 5:
                continue
            pop = float(m.get("popularity", 0)) if pd.notna(m.get("popularity")) else 0
            if pop <= 1.75:
                continue
            gs = str(m.get("genres", "")) if pd.notna(m.get("genres")) else ""
            if any(g in gs.lower() for g in ["tv movie", "documentary"]):
                continue
            mid = None
            try:
                mid = int(m.get("id"))
            except Exception:
                pass
            top.append((normalize_title(m.get("title", "")), mid))
            if len(top) >= max(KS):
                break

        for k in KS:
            tk = top[:k]
            hits = [
                ((mid in gt_id) if mid else False) or (nt in gt_norm)
                for nt, mid in tk
            ]
            recalls[k].append(sum(hits) / max(len(gts), 1))
            first = next((1.0 / (i + 1) for i, h in enumerate(hits) if h), 0.0)
            mrrs[k].append(first)
            rels = [gt_id.get(mid, gt_norm_rel.get(nt, 0.0)) for nt, mid in tk]
            ndcgs[k].append(ndcg_at_k(rels, k))

    all_results[model_name] = {
        "recall": {k: float(np.mean(recalls[k])) for k in KS},
        "mrr": {k: float(np.mean(mrrs[k])) for k in KS},
        "ndcg": {k: float(np.mean(ndcgs[k])) for k in KS},
        "skipped": skipped,
    }

    print(f"\n{model_name} ({skipped} anchors skipped):")
    for k in KS:
        r = all_results[model_name]
        print(f"  @{k:>2}: Recall={r['recall'][k]:.1%}  MRR={r['mrr'][k]:.3f}  nDCG={r['ndcg'][k]:.3f}")

print("\n=== COMPARISON ===")
for k in KS:
    m = all_results.get("MiniLM", {})
    mp = all_results.get("MPNet", {})
    if m and mp:
        diff_r = (mp["recall"][k] - m["recall"][k]) / max(m["recall"][k], 1e-9) * 100
        print(f"  Recall@{k}: MiniLM={m['recall'][k]:.1%}  MPNet={mp['recall'][k]:.1%}  Diff={diff_r:+.1f}%")
        print(f"  MRR@{k}:    MiniLM={m['mrr'][k]:.3f}  MPNet={mp['mrr'][k]:.3f}")
        print(f"  nDCG@{k}:   MiniLM={m['ndcg'][k]:.3f}  MPNet={mp['ndcg'][k]:.3f}")
