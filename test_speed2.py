import time
import sys
import os
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from data_loader import get_data
import difflib

df, title_to_index, index = get_data()
all_titles = list(title_to_index.keys())

# Test id_to_index creation
print("Testing Dictionary Creation...")
start = time.time()
id_to_index = pd.Series(df.index, index=df['id'].astype(str)).to_dict()
print(f"Dict created in {time.time() - start:.2f}s")

tmdb_id = "155"
start = time.time()
for _ in range(15):
    idx = id_to_index.get(str(tmdb_id))
print(f"Dict lookup 15x took {time.time() - start:.5f}s")  # expect ~0.00001s

# Test fast fuzzy matching
query = "batman"
start = time.time()
# get_close_matches is implemented in C and is generally faster, but let's test.
# wait, actually get_close_matches might still take a few seconds on 1M items
matches = difflib.get_close_matches(query, all_titles, n=10, cutoff=0.5)
print(f"difflib.get_close_matches took {time.time() - start:.2f}s")

