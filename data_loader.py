# data_loader.py
import pandas as pd
import os
import kagglehub
from sklearn.feature_extraction.text import TfidfVectorizer
import pickle
import faiss

# Export everything
def get_data():
    with open('index_data.pkl', 'rb') as f:
        data = pickle.load(f)
    
    df = data['df']
    embeddings = data['embeddings']
    title_to_index = data['title_to_index']
    index = faiss.read_index('faiss.index')

    return df, embeddings, title_to_index, index
