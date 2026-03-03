import pickle
import numpy as np
import faiss
import pandas as pd

print("Loading data...")
with open('index_data.pkl', 'rb') as f:
    data = pickle.load(f)

df = data['df']
title_to_index = data['title_to_index']

# Find all movies with 'parasite' in title to ensure we have the right one
print("Matches for 'parasite':")
matches = df[df['title'].str.lower().str.contains('parasite', na=False)]
for _, row in matches.iterrows():
    print(f"ID: {row.name}, Title: {row['title']}, Year: {row['release_date']}, Pop: {row['popularity']}, Votes: {row['vote_count']}")

parasite_idx = title_to_index.get('parasite')
print(f"\nTarget Index for 'parasite': {parasite_idx}")

if parasite_idx is not None:
    print("\nLoading FAISS...")
    try:
        index = faiss.read_index('faiss.index') # Without MMAP to avoid memory fragmentation issues in this isolate script
    except Exception as e:
        print(f"Could not load index normally: {e}. Trying MMAP...")
        index = faiss.read_index('faiss.index', faiss.IO_FLAG_MMAP)
        
    print(f"Index loaded. Total vectors: {index.ntotal}")
    
    parasite_embedding = np.array([index.reconstruct(parasite_idx)])
    distances, indices = index.search(parasite_embedding, 10)
    
    print("\nTop 10 Recommendations for Parasite (idx {}):".format(parasite_idx))
    for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
        if idx != -1:
            movie = df.iloc[idx]
            print(f"{i+1}. {movie['title']} ({movie['release_date']}) - Distance: {dist:.4f}")
            print(f"   Genres: {movie['genres']}")
            print(f"   Keywords: {movie['keywords']}")
            print(f"   Overview Snippet: {str(movie['overview'])[:100]}...")
            print()
