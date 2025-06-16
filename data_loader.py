# data_loader.py
import pandas as pd
import os
import kagglehub
from sklearn.feature_extraction.text import TfidfVectorizer
import pickle
import faiss

def get_basic_data():
    import pandas as pd
    from data_utils import get_dataset_path

    csv_file = get_dataset_path()
    df = pd.read_csv(csv_file)
    df['title'] = df['title'].fillna('')
    df['overview'] = df['overview'].fillna('')
    return df

# Export everything
def get_data():
    with open('index_data.pkl', 'rb') as f:
        data = pickle.load(f)
    
    df = data['df']
    embeddings = data['embeddings']
    title_to_index = data['title_to_index']
    index = faiss.read_index('faiss.index')

    return df, embeddings, title_to_index, index
