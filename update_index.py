# update_index.py
import pandas as pd
import numpy as np
import faiss
import pickle
from sentence_transformers import SentenceTransformer
import os
import torch
from data_utils import get_dataset_path

torch.set_num_threads(2)

# ---------------- Configuration ---------------- #
INDEX_FILE = 'faiss.index'
DATA_FILE = 'index_data.pkl'
csv_file = get_dataset_path()
device = 'cuda' if torch.cuda.is_available() else 'cpu'

# --- 1. Check if an index exists. If not, exit. ---
if not os.path.exists(INDEX_FILE) or not os.path.exists(DATA_FILE):
    print("⚠️ Index files not found. Please run build_index.py first.")
    exit()

# --- 2. Load existing index and data ---
print("✅ Loading existing index and data...")
index = faiss.read_index(INDEX_FILE)
with open(DATA_FILE, 'rb') as f:
    data = pickle.load(f)
    df_existing = data['df']
    title_to_index = data['title_to_index']

print(f"Index currently contains {index.ntotal} movies.")

# --- 3. Load the new CSV and identify new movies ---
df_new_full = pd.read_csv(csv_file)
# Find titles in the new CSV that are NOT in our existing title map
existing_titles = set(title_to_index.keys())
new_titles_mask = ~df_new_full['title'].str.lower().isin(existing_titles)
df_new = df_new_full[new_titles_mask]

if df_new.empty:
    print("✅ No new movies found to add. Index is up-to-date.")
    exit()

print(f"Found {len(df_new)} new movies to add.")

# --- 4. Process and encode ONLY the new movies ---
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

def combine_text(row):
    genres = row['genres'] if pd.notna(row['genres']) else ''
    keywords = row['keywords'] if pd.notna(row['keywords']) else ''
    overview = row['overview'] if pd.notna(row['overview']) else ''
    return f"{genres} {genres} {genres} {keywords} {keywords} {overview}"

texts_new = df_new.apply(combine_text, axis=1).tolist()

print("✅ Encoding new movies...")
new_embeddings = model.encode(
    texts_new,
    normalize_embeddings=True,
    device=device,
    show_progress_bar=True
)
new_embeddings = np.array(new_embeddings).astype('float32')

# --- 5. Add new embeddings to the FAISS index ---
print("✅ Adding new embeddings to FAISS index...")
index.add(new_embeddings)

# --- 6. Append new data and update title map ---
print("✅ Updating DataFrame and metadata...")
# Important: reset index for clean concatenation
df_new.reset_index(drop=True, inplace=True)
df_updated = pd.concat([df_existing, df_new], ignore_index=True)

# Update the title-to-index map
current_index_size = len(df_existing)
for i, title in enumerate(df_new['title'].fillna('').tolist()):
    # New indices start after the last old index
    title_to_index[title.lower()] = current_index_size + i

# --- 7. Save the updated index and data ---
print("✅ Saving updated files...")
faiss.write_index(index, INDEX_FILE)

with open(DATA_FILE, 'wb') as f:
    pickle.dump({
        'df': df_updated,
        'title_to_index': title_to_index
    }, f)

print(f"🎉 Update complete. Index now contains {index.ntotal} movies.")