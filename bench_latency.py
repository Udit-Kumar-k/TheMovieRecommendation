# bench_latency.py
"""
Latency Benchmark: Measures the inference penalty of MPNet vs MiniLM.
Encodes 500 random movie overviews with each model and compares avg latency per query.
"""
import sys
import time
import random
import pickle
import os
import torch
from sentence_transformers import SentenceTransformer

# Ensure Windows terminals can print Unicode (emojis, accents)
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ------- Load 500 random overviews from the dataset ------- #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Try loading from any available index_data.pkl (we just need overviews)
for path in ['models/minilm/index_data.pkl', 'models/mpnet/index_data.pkl', 'index_data.pkl']:
    full_path = os.path.join(BASE_DIR, path)
    if os.path.exists(full_path):
        with open(full_path, 'rb') as f:
            data = pickle.load(f)
        break
else:
    print("❌ No index_data.pkl found. Build at least one index first.")
    exit(1)

df = data['df']
all_overviews = df['overview'].dropna().tolist()
all_overviews = [o for o in all_overviews if o.strip()]

SAMPLE_SIZE = 500
random.seed(42)
sample = random.sample(all_overviews, min(SAMPLE_SIZE, len(all_overviews)))
print(f"📦 Loaded {len(sample)} random overviews for benchmarking.\n")

# ------- Define models to benchmark ------- #
models_to_test = [
    ('MiniLM (all-MiniLM-L6-v2)', 'all-MiniLM-L6-v2'),
    ('MPNet (all-mpnet-base-v2)', 'sentence-transformers/all-mpnet-base-v2'),
]

device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"🖥️  Device: {device}\n")

results = []

for display_name, model_name in models_to_test:
    print(f"⏳ Loading {display_name}...")
    model = SentenceTransformer(model_name)
    
    # Warmup: encode a small dummy batch to JIT compile / warm GPU caches
    _ = model.encode(["warmup sentence"], device=device, normalize_embeddings=True)
    if torch.cuda.is_available():
        torch.cuda.synchronize()

    print(f"🚀 Encoding {len(sample)} overviews with {display_name}...")
    start = time.time()
    
    model.encode(sample, device=device, normalize_embeddings=True, batch_size=32)
    
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    
    elapsed = time.time() - start
    avg_ms = (elapsed / len(sample)) * 1000
    
    results.append({
        'model': display_name,
        'total_time': elapsed,
        'avg_ms': avg_ms,
    })
    
    print(f"   ✅ Done in {elapsed:.2f}s (avg {avg_ms:.2f} ms/query)\n")
    
    # Free memory before loading next model
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

# ------- Print Results Table ------- #
print("\n" + "=" * 65)
print("  LATENCY BENCHMARK RESULTS")
print("=" * 65)
print(f"  {'Model':<35} {'Total (s)':<12} {'Avg (ms/q)':<12}")
print("-" * 65)

for r in results:
    print(f"  {r['model']:<35} {r['total_time']:<12.2f} {r['avg_ms']:<12.2f}")

if len(results) == 2:
    speedup = results[1]['avg_ms'] / results[0]['avg_ms']
    penalty = ((results[1]['avg_ms'] - results[0]['avg_ms']) / results[0]['avg_ms']) * 100
    print("-" * 65)
    print(f"  MPNet Inference Penalty: {penalty:+.1f}% slower ({speedup:.2f}x latency)")
    
print("=" * 65)
