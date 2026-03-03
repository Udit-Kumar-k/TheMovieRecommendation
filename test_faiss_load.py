import faiss
import os

try:
    print("Loading faiss index with mmap...")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    index = faiss.read_index(os.path.join(BASE_DIR, 'faiss.index'), faiss.IO_FLAG_MMAP)
    print("Success! Index type:", type(index))
except Exception as e:
    print("Error:", e)
