import sys
import platform
import os
import faiss
import pickle
import psutil

print("Python Architecture:", platform.architecture())
print("Available Memory:", psutil.virtual_memory().available / (1024**3), "GB")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print("\n--- Try loading FAISS BEFORE pickle ---")
try:
    print("1. Mapping FAISS...")
    index = faiss.read_index(os.path.join(BASE_DIR, 'faiss.index'), faiss.IO_FLAG_MMAP)
    print("   Success! mapped", getattr(index, 'ntotal', '?'), "vectors.")
    print("2. Loading Pickle...")
    with open(os.path.join(BASE_DIR, 'index_data.pkl'), 'rb') as f:
        data = pickle.load(f)
    print("   Success!")
except Exception as e:
    print("Failed in FAISS first:", e)
    
print("\nDone testing memory limits.")
