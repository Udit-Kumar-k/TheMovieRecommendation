# data_loader.py
import pandas as pd
import os
import kagglehub
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# Download + load dataset
dataset_path = kagglehub.dataset_download("alanvourch/tmdb-movies-daily-updates")
csv_file = os.path.join(dataset_path, "TMDB_all_movies.csv")

# Load data
df = pd.read_csv(csv_file)
df = df.reset_index(drop=True)

df['overview'] = df['overview'].fillna('')
df['genres'] = df['genres'].fillna('')
df['text_data'] = df['overview']

# Load model + encode if not already saved
model = SentenceTransformer('all-MiniLM-L6-v2')
emb_path = "embeddings.npy"

if os.path.exists(emb_path):
    embeddings = np.load(emb_path)
else:
    embeddings = model.encode(df['text_data'].tolist(), show_progress_bar=True, convert_to_numpy=True)
    np.save(emb_path, embeddings)

# Normalize embeddings for cosine similarity
embeddings = embeddings.astype('float32')
faiss.normalize_L2(embeddings)

# Build FAISS index
index = faiss.IndexFlatIP(embeddings.shape[1])  # Inner product = cosine if normalized
index.add(embeddings)

# Map titles
indices = pd.Series(df.index, index=df['title'].str.lower()).drop_duplicates()

def get_data():
    return df, index, embeddings, indices
