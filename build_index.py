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
import argparse
from data_utils import get_dataset_path

# ----------------  CLI Arguments  ---------------- #
parser = argparse.ArgumentParser(description='Build FAISS index with a chosen embedding model.')
parser.add_argument('--model', type=str, default='minilm', choices=['minilm', 'mpnet'],
                    help='Embedding model to use: minilm (fast) or mpnet (accurate)')
parser.add_argument('--output-dir', type=str, default='.',
                    help='Directory to save faiss.index and index_data.pkl (default: current dir)')
args = parser.parse_args()

# ----------------  Model Config  ---------------- #
MODEL_CONFIG = {
    'minilm': {
        'name': 'all-MiniLM-L6-v2',
        'batch_size': 32,
        'sleep_between_batches': 0,       # No throttle
        'checkpoint_interval': 125,        # Save every 125 batches
    },
    'mpnet': {
        'name': 'sentence-transformers/all-mpnet-base-v2',
        'batch_size': 16,                  # Smaller batches for 4GB VRAM safety
        'sleep_between_batches': 1.0,      # 1 second cooldown between batches
        'checkpoint_interval': 50,         # Frequent auto-saves
    }
}

config = MODEL_CONFIG[args.model]
print(f"\n{'='*50}")
print(f"  Building index with: {config['name']}")
print(f"  Output directory:    {args.output_dir}")
print(f"  Batch size:          {config['batch_size']}")
print(f"  Sleep between:       {config['sleep_between_batches']}s")
print(f"  Checkpoint every:    {config['checkpoint_interval']} batches")
print(f"{'='*50}\n")

# Ensure output directory exists
os.makedirs(args.output_dir, exist_ok=True)

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

# Converter strings to ints safely, then keep only >= 5 votes
# (Kaggle dataset has some NaNs or floats here)
df['vote_count'] = pd.to_numeric(df['vote_count'], errors='coerce').fillna(0)
df = df[df['vote_count'] >= 5]
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
model = SentenceTransformer(config['name'])
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"✅ Using device: {device}")

# Checkpoint lives INSIDE the output dir so parallel builds don't collide
checkpoint_file = os.path.join(args.output_dir, 'embeddings_checkpoint.pkl')
embeddings = []
start_idx = 0

if os.path.exists(checkpoint_file):
    print("🔄 Found checkpoint file! Loading previously saved embeddings...")
    with open(checkpoint_file, 'rb') as f:
        embeddings = pickle.load(f)
    start_idx = len(embeddings)
    print(f"✅ Resuming exactly where we left off: item {start_idx} / {len(texts)}")

batch_size = config['batch_size']
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

        # Cooldown between batches (0 for MiniLM, 1s for MPNet)
        if config['sleep_between_batches'] > 0:
            time.sleep(config['sleep_between_batches'])
        
        # Clear CUDA cache every batch for MPNet, periodically for MiniLM
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Auto-save checkpoint at the configured interval
        batches_done = (i - start_idx) // batch_size + 1
        if batches_done % config['checkpoint_interval'] == 0 or len(embeddings) >= total:
            with open(checkpoint_file, 'wb') as f:
                pickle.dump(embeddings, f)
            print(f"💾 Checkpoint Auto-Saved! ({len(embeddings)} / {total})")

        batch_time = time.time() - batch_start
        items_left = total - len(embeddings)
        batches_left = items_left / batch_size
        eta_mins = (batches_left * batch_time) / 60
        print(f"✅ Encoded {len(embeddings)} / {total} | Batch time: {batch_time:.2f}s | ETA: {eta_mins:.1f} mins")

    except RuntimeError as e:
        # Emergency save on crash
        with open(checkpoint_file, 'wb') as f:
            pickle.dump(embeddings, f)
        print(f"\n💾 Emergency checkpoint saved! ({len(embeddings)} / {total})")
        print(f"⚠️ Batch {i}-{i+batch_size} failed. Error: {e}")
        break

# ---------------- Save FAISS Index ---------------- #
embeddings = np.array(embeddings).astype('float32')
dimension = embeddings.shape[1]
index = faiss.IndexFlatIP(dimension)
index.add(embeddings)

output_index = os.path.join(args.output_dir, 'faiss.index')
faiss.write_index(index, output_index)

# ---------------- Save DataFrame + Embeddings ---------------- #
output_pkl = os.path.join(args.output_dir, 'index_data.pkl')
with open(output_pkl, 'wb') as f:
    pickle.dump({
        'df': df,
        'title_to_index': {title.lower(): i for i, title in enumerate(df['title'].fillna('').tolist())}
    }, f)

if os.path.exists(checkpoint_file):
    os.remove(checkpoint_file)
    print("🧹 Cleaned up temporary checkpoint file.")

print(f"\n✅ Index build complete! Files saved to: {args.output_dir}/")
print(f"   → {output_index}")
print(f"   → {output_pkl}")
