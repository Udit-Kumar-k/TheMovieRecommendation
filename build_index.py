# build_index.py
import pandas as pd
import numpy as np
import faiss
import pickle
from sentence_transformers import SentenceTransformer
import os
import kagglehub
import torch
import time
from data_utils import get_dataset_path


torch.set_num_threads(2)

# ---------------- Load & Prepare Dataset ---------------- #
if os.path.exists('healed_tmdb_dataset.csv'):
    csv_file = 'healed_tmdb_dataset.csv'
    print(f"Loading HEALED pristine dataset from: {csv_file}")
else:
    csv_file = get_dataset_path()
    print(f"Loading raw Kaggle dataset from: {csv_file}")

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

# Filter out TV Movies and Documentaries
df = df[~df['genres'].str.contains('TV Movie|Documentary', case=False, na=False)]

def combine_text(row):
    overview = row['overview'] or ''
    keywords = row['keywords'] or ''
    genres = row['genres'] or ''

    return f"Genres: {genres}. Keywords: {keywords}. Overview: {overview}"

texts = df.apply(combine_text, axis=1).tolist()

# ---------------- Embedding Model Selection ---------------- #
# Uncomment the model you want to use to build the index:

# 1. MiniLM (Faster, lighter, uses less VRAM, 384 dimensions)
model = SentenceTransformer('all-MiniLM-L6-v2')

# 2. MPNet (Slower, heavier, more accurate, 768 dimensions)
# model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"✅ Using device: {device}")

checkpoint_file = 'embeddings_checkpoint.pkl'
embeddings = []
start_idx = 0

if os.path.exists(checkpoint_file):
    print("🔄 Found checkpoint file! Loading previously saved embeddings...")
    with open(checkpoint_file, 'rb') as f:
        embeddings = pickle.load(f)
    start_idx = len(embeddings)
    print(f"✅ Resuming exactly where we left off: item {start_idx} / {len(texts)}")

batch_size = 32  # Reduced for 4GB VRAM safety with heavier MPNet
total = len(texts)

for i in range(start_idx, total, batch_size):
    batch_start = time.time()
    batch = texts[i:i+batch_size]
    
    try:
        batch_embeddings = model.encode(
            batch,
            normalize_embeddings=True,
            device=device
        )
        embeddings.extend(batch_embeddings)

        # Pause to let GPU cool down and decrease load over time
        # time.sleep(1.0) 
        
        # Clear CUDA cache periodically to free VRAM
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Auto-save checkpoint every ~100 batches
        batches_done = (i - start_idx) // batch_size + 1
        if batches_done % 125 == 0 or len(embeddings) >= total:
            with open(checkpoint_file, 'wb') as f:
                pickle.dump(embeddings, f)
            print(f"💾 Checkpoint Auto-Saved! ({len(embeddings)} / {total})")

        batch_time = time.time() - batch_start
        items_left = total - len(embeddings)
        batches_left = items_left / batch_size
        eta_mins = (batches_left * batch_time) / 60
        print(f"✅ Encoded {len(embeddings)} / {total} | Batch time: {batch_time:.2f}s | ETA: {eta_mins:.1f} mins")

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

if os.path.exists(checkpoint_file):
    os.remove(checkpoint_file)
    print("🧹 Cleaned up temporary checkpoint file.")

print("✅ Initial Index build complete.")
