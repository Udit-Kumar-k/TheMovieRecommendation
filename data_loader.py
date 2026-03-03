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
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Load DataFrame and indices from the optimized pickle file (only 73MB)
    # This prevents the huge MemoryError Pandas throws when parsing the 500MB CSV file on Windows!
    with open(os.path.join(BASE_DIR, 'index_data.pkl'), 'rb') as f:
        data = pickle.load(f)
        df = data['df']
        title_to_index = data['title_to_index']
    
    # Load FAISS Index without MMAP to prevent contiguous memory allocation failures
    index = faiss.read_index(os.path.join(BASE_DIR, 'faiss.index'))

    return df, title_to_index, index
