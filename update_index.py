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

if os.path.exists('healed_tmdb_dataset.csv'):
    csv_file = 'healed_tmdb_dataset.csv'
    print(f"Loading HEALED pristine dataset from: {csv_file}")
else:
    csv_file = get_dataset_path()
    print(f"Loading raw Kaggle dataset from: {csv_file}")

device = 'cuda' if torch.cuda.is_available() else 'cpu'

# --- 1. Check if an index exists. If not, exit. ---
if not os.path.exists(INDEX_FILE) or not os.path.exists(DATA_FILE):
    print("⚠️ Index files not found. Please run build_index.py first.")
    exit()

# --- 2. Load existing index and data ---
print("✅ Loading existing index and data...")
index = faiss.read_index(INDEX_FILE, faiss.IO_FLAG_MMAP)

print("✅ Loading dataframe from index_data.pkl to match actual FAISS index...")
with open(DATA_FILE, 'rb') as f:
    data = pickle.load(f)
    df_existing = data['df']
    title_to_index = data['title_to_index']

print(f"Index currently contains {index.ntotal} movies.")

# --- 3. Load the new CSV and identify new movies ---
df_new_full = pd.read_csv(csv_file)
df_new_full = df_new_full[df_new_full['popularity'] > 1.75]
df_new_full = df_new_full.dropna(subset=['overview'])
df_new_full = df_new_full[df_new_full['overview'].str.strip() != '']

# Filter out TV Movies and Documentaries
df_new_full['genres'] = df_new_full['genres'].fillna('')
df_new_full = df_new_full[~df_new_full['genres'].str.contains('TV Movie|Documentary', case=False, na=False)]

df_new_full['vote_count'] = pd.to_numeric(df_new_full['vote_count'], errors='coerce').fillna(0)
df_new_full = df_new_full[df_new_full['vote_count'] >= 5]
df_new_full = df_new_full[df_new_full['vote_average'] < 10]

# Filter out older movies with NO ratings while keeping upcoming releases
from datetime import datetime
current_year = datetime.now().year
df_new_full['release_year'] = pd.to_datetime(df_new_full['release_date'], errors='coerce').dt.year

has_ratings = df_new_full['vote_average'] > 0
is_recent = df_new_full['release_year'] >= (current_year - 2)
df_new_full = df_new_full[has_ratings | is_recent]

df_new_full = df_new_full.drop(columns=['release_year'])

# Find movies in the new CSV that are NOT in our existing index by ID
existing_ids = set(df_existing['id'].dropna().astype(int).astype(str))
df_new_full['str_id'] = df_new_full['id'].dropna().astype(int).astype(str)
new_ids_mask = ~df_new_full['str_id'].isin(existing_ids)
df_new = df_new_full[new_ids_mask]
df_new = df_new.drop(columns=['str_id'])

if df_new.empty:
    print("✅ No new movies found to add. Index is up-to-date.")
    exit()

print(f"Found {len(df_new)} new movies to add.")

# --- 4. Process and encode ONLY the new movies ---
# ---------------- Embedding Model Selection ---------------- #
# IMPORTANT: This MUST match the model you used in build_index.py!

# 1. MiniLM (Faster, lighter, uses less VRAM, 384 dimensions)
model = SentenceTransformer('all-MiniLM-L6-v2')

# 2. MPNet (Slower, heavier, more accurate, 768 dimensions)
# model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

def combine_text(row):
    overview = row['overview'] if pd.notna(row['overview']) else ''
    keywords = row['keywords'] if pd.notna(row['keywords']) else ''
    genres = row['genres'] if pd.notna(row['genres']) else ''

    return f"Genres: {genres}. Keywords: {keywords}. Overview: {overview}"

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