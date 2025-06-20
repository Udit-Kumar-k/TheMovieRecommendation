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


#torch.set_num_threads(2)

# ---------------- Load & Prepare Dataset ---------------- #
csv_file = get_dataset_path()

df = pd.read_csv(csv_file)
df['overview'] = df['overview'].fillna('')
df['genres'] = df['genres'].fillna('')
df['keywords'] = df['keywords'].fillna('')

def combine_text(row):
    return f"{row['overview']} {row['genres']} {row['keywords']}"

texts = df.apply(combine_text, axis=1).tolist()

# ---------------- Embedding with MiniLM ---------------- #
print("✅ Using CPU")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

print("✅ Encoding started...")
embeddings = model.encode(
    texts,
    show_progress_bar=True,
    normalize_embeddings=True,
    batch_size=32
)
print("✅ Encoding done!")

# ---------------- Save FAISS Index ---------------- #
embeddings = np.array(embeddings).astype('float32')
dimension = embeddings.shape[1]
index = faiss.IndexFlatIP(dimension)
index.add(embeddings)
faiss.write_index(index, 'faiss.index')

# ---------------- Save DataFrame + Embeddings ---------------- #
with open('index_data.pkl', 'wb') as f:
    pickle.dump({
        'df': df,
        'embeddings': embeddings,
        'title_to_index': {title.lower(): i for i, title in enumerate(df['title'].fillna('').tolist())},
        'faiss_index': index
    }, f)

print("✅ Index build complete.")
