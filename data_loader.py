# data_loader.py
import pandas as pd
import os
import kagglehub
from sklearn.feature_extraction.text import TfidfVectorizer

# Download + load dataset
dataset_path = kagglehub.dataset_download("alanvourch/tmdb-movies-daily-updates")
csv_file = os.path.join(dataset_path, "TMDB_all_movies.csv")

df = pd.read_csv(csv_file)
df['overview'] = df['overview'].fillna('')
df['genres'] = df['genres'].fillna('')
df['text_data'] = df['overview'] + ' ' + df['genres']

# TF-IDF processing
tfidf = TfidfVectorizer(stop_words='english', max_features=5000)
tfidf_matrix = tfidf.fit_transform(df['text_data'])

# Index mapping
indices = pd.Series(df.index, index=df['title'].str.lower()).drop_duplicates()

# Export everything
def get_data():
    return df, tfidf_matrix, indices
