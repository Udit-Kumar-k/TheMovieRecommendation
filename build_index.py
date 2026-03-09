# build_index.py
import pandas as pd
import numpy as np
import faiss
import pickle
from sentence_transformers import SentenceTransformer
import os
import kagglehub
import torch
from data_utils import get_dataset_path


torch.set_num_threads(2)

# ---------------- Load & Prepare Dataset ---------------- #
csv_file = get_dataset_path()

df = pd.read_csv(csv_file)
df = df[df['popularity'] > 1.75]

# Filter out movies that have NO overview (empty or pure whitespace)
df = df.dropna(subset=['overview'])
df = df[df['overview'].str.strip() != '']

# Filter out older movies with NO ratings while keeping upcoming releases
from datetime import datetime
current_year = datetime.now().year

# Convert release_date to datetime to extract year safely
df['release_year'] = pd.to_datetime(df['release_date'], errors='coerce').dt.year

# Converter strings to ints safely, then keep only >= 2 votes
# (Kaggle dataset has some NaNs or floats here)
df['vote_count'] = pd.to_numeric(df['vote_count'], errors='coerce').fillna(0)
df = df[df['vote_count'] > 1]
df = df[df['vote_average'] < 10]

# Keep a movie IF:
# 1. It came out in the last 2 years, this year, or in the future
# 2. OR it actually has some votes (vote_average > 0 and vote_count > 1)
has_ratings = df['vote_average'] > 0
is_recent = df['release_year'] >= (current_year - 2)
df = df[has_ratings | is_recent]

# Clean up the temporary column
df = df.drop(columns=['release_year'])

df['overview'] = df['overview'].fillna('')
df['genres'] = df['genres'].fillna('')
df['keywords'] = df['keywords'].fillna('')

def combine_text(row):
    overview = row['overview'] or ''
    keywords = row['keywords'] or ''
    genres = row['genres'] or ''

    return f"Genres: {genres}. Keywords: {keywords}. Overview: {overview}"

texts = df.apply(combine_text, axis=1).tolist()

# ---------------- Embedding with MiniLM ---------------- #
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"✅ Using device: {device}")

embeddings = []
batch_size = 64
total = len(texts)

for i in range(0, total, batch_size):
    batch = texts[i:i+batch_size]
    
    try:
        batch_embeddings = model.encode(
            batch,
            normalize_embeddings=True,
            device=device
        )
        embeddings.extend(batch_embeddings)

        print(f"✅ Encoded {min(i + batch_size, total)} / {total}")

    except RuntimeError as e:
        print(f"\n⚠️ Batch {i}-{i+batch_size} failed. Consider lowering batch_size (currently {batch_size}).\nError: {e}")
        break

# ---------------- Save FAISS Index ---------------- #
embeddings = np.array(embeddings).astype('float32')
dimension = embeddings.shape[1]
index = faiss.IndexFlatIP(dimension)
index.add(embeddings)
faiss.write_index(index, 'faiss.index')

# ---------------- Save DataFrame + Embeddings ---------------- #d
with open('index_data.pkl', 'wb') as f:
    pickle.dump({
        'df': df,
        'title_to_index': {title.lower(): i for i, title in enumerate(df['title'].fillna('').tolist())}
    }, f)

print("✅ Initial Index build complete.")
