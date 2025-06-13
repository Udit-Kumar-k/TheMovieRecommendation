# data_loader.py
import pandas as pd
import os
import kagglehub
from sentence_transformers import SentenceTransformer

# Download + load dataset
dataset_path = kagglehub.dataset_download("alanvourch/tmdb-movies-daily-updates")
csv_file = os.path.join(dataset_path, "TMDB_all_movies.csv")

# Load data
df = pd.read_csv(csv_file)

# Limit + reset index
df = df.head(10000).reset_index(drop=True)

df['overview'] = df['overview'].fillna('')
df['genres'] = df['genres'].fillna('')
df['text_data'] = df['overview']
  # Use only overview for semantic meaning

# Load sentence-transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Generate embeddings
embeddings = model.encode(df['text_data'].tolist(), show_progress_bar=True)

# Index mapping
indices = pd.Series(df.index, index=df['title'].str.lower()).drop_duplicates()

# Export data
def get_data():
    return df, embeddings, indices
print("Titles available:", df['title'].str.lower().str.strip().tolist()[:40])

