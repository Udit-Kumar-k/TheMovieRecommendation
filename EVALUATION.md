# Evaluation Framework

## Evaluation Overview

This system evaluates movie recommendations across three complementary dimensions. First, a hand-curated golden dataset measures semantic retrieval quality — whether the model surfaces genuinely relevant films for a given anchor. Second, a Jaccard genre ablation study (`bench_jaccard.py`) isolates the contribution of the 25% genre boost applied on top of raw FAISS cosine similarity, proving or disproving that genre alignment improves domain relevance. Third, a TMDB overlap benchmark (`bench_tmdb_overlap.py`) compares our recommendations against TMDB's own recommendation API as an industry reference point — not an optimization target.

---

## Dataset Construction Methodology

Ground truth pairs were selected **before** running any benchmarks to prevent label leakage. The dataset is divided into four categories:

| Category | Anchors | Ground Truths per Anchor | Description |
|---|---|---|---|
| Franchise / obvious pairs | 20 | 3 | Same franchise, director, or cinematic universe |
| Cross-genre semantic pairs | 20 | 5 | Genuine thematic similarity beyond genre tags |
| Hard cases | 25 | 5 | Non-obvious matches requiring deep semantic understanding |
| Bollywood / regional | 35 | 5 | Indian and non-English films for diversity coverage |

The franchise anchors (Dark Knight trilogy, Harry Potter, Lord of the Rings, MCU arcs, Pixar sequels, etc.) serve as **sanity checks** — a correctly functioning semantic retrieval system must be able to find sequels and companion films. The cross-genre semantic pairs and hard cases were hand-selected by the author to reflect genuine thematic similarity beyond genre labels. A production system would use multiple annotators with inter-rater agreement scoring.

---

## Metrics

| Metric | What it measures |
|---|---|
| **Recall@5** | Coverage of ground truth at a tight cutoff. With 5 GT items, this is the strictest useful measure. |
| **Recall@10** | Coverage at a looser cutoff — how many GT items appear anywhere in the top 10. |
| **nDCG@10** | Ranking quality. Penalises relevant results that appear too far down the list; uses graded relevance scores. |
| **MRR@10** | Reciprocal rank of the **first** relevant result. Answers: "How quickly does the model surface anything useful?" |
| **TMDB Overlap@10** | Number of titles in common between our top-10 and TMDB's top-10 (raw intersection size). |
| **TMDB Jaccard@10** | Set similarity against TMDB: \|intersection\| / \|union\|. Scale 0–1; higher ≠ better quality. |

---

## Results

> Benchmarked on `golden_dataset.json` (100 anchors: 20 franchise, 20 cross-genre, 25 hard cases, 35 Bollywood/regional).
> Raw FAISS cosine similarity only — no Jaccard boost, no quality sorting applied during evaluation. 4 anchors skipped (not found in index).

| Model | Recall@5 | Recall@10 | nDCG@5 | nDCG@10 | MRR@5 | MRR@10 | TMDB Overlap@10 | TMDB Jaccard@10 | Latency ms/query |
|---|---|---|---|---|---|---|---|---|---|
| MiniLM | 14.7% | 17.9% | 0.232 | 0.235 | 0.220 | 0.225 | 1.05 | 0.063 | **1.72** |
| MPNet  | 15.8% | 18.7% | 0.235 | 0.247 | 0.222 | 0.230 | 1.05 | 0.063 | 10.56 |

---

## Jaccard Genre Boost Ablation

> Measures whether the 25% genre Jaccard boost applied on top of raw FAISS cosine similarity actually improves genre alignment in the top-10 results.
> Benchmarked on full golden dataset (100 anchors) using MiniLM index.

| Condition | Genre Alignment Rate (Top 10) |
|---|---|
| Raw FAISS — no genre boost | ~96% |
| +25% Jaccard genre boost (production) | **98.8%** |

**Result:** The genre boost moves alignment from ~96% → 98.8% — a meaningful improvement in domain relevance, especially for genre-specific anchors.

---

## MiniLM vs MPNet Tradeoff

Both models were benchmarked on identical data, identical quality filters, and identical FAISS indices built from the same 90k-movie TMDB dataset. MPNet showed a **+513.9% latency penalty** over MiniLM (6.14× slower: 1.72 ms vs 10.56 ms per query), with a modest quality gain of **+8.1% Recall@5** and **+4.3% Recall@10**. Based on this tradeoff, **MiniLM was selected for production deployment** — it delivers comparable semantic accuracy at a fraction of the inference cost, making it the right choice for a real-time web serving context.

---

## Known Limitations

- The cross-genre semantic and hard-case ground truth reflects **one annotator's judgments**. A production-grade evaluation would use multiple annotators with inter-rater agreement scoring such as **Cohen's Kappa** to validate label consistency.
- The 20 franchise anchors are intentionally easy cases, included to **verify baseline retrieval sanity** — not to inflate overall scores. They should be excluded from aggregate metrics when reporting semantic retrieval performance.
- TMDB overlap metrics measure alignment with one commercial recommendation system. TMDB's algorithm weighs user co-watch behaviour, which prioritises popularity and genre proximity over thematic depth. Agreement with TMDB is not a measure of quality; disagreement is not a defect.
