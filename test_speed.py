import time
import sys
import os

# Append current dir so we can import app code
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_loader import get_data
from difflib import SequenceMatcher

print("Loading data...")
start = time.time()
df, title_to_index, index = get_data()
print(f"Data loaded in {time.time() - start:.2f}s")
print(f"Total titles: {len(title_to_index)}")

print("Testing fuzzy matching speed...")
query = "batman"
start = time.time()
all_titles = list(title_to_index.keys())
similarities = []
for title in all_titles:
    ratio = SequenceMatcher(None, query, title).ratio()
    if ratio > 0.5:
        similarities.append((title, ratio))
print(f"Fuzzy match took {time.time() - start:.2f}s")

print("Testing Pandas column astype speed (x15 times like enrich_tmdb_results)...")
tmdb_id = "155"
start = time.time()
for _ in range(15):
    matches = df.index[df['id'].astype(str) == str(tmdb_id)].tolist()
print(f"Pandas ID lookup (15x) took {time.time() - start:.2f}s")

