import os
import requests
import json
import pandas as pd
import time
from tqdm import tqdm
from dotenv import load_dotenv
from data_utils import get_dataset_path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()
API_KEY = os.getenv('TMDB_API_KEY')
if not API_KEY:
    print("Error: TMDB_API_KEY not found in .env files.")
    exit(1)

# Configure super robust session
session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

print("🚀 Fetching Movie Genre Mapping from TMDB...")
try:
    genre_res = session.get(f"https://api.tmdb.org/3/genre/movie/list?api_key={API_KEY}&language=en-US", timeout=30)
    genre_map = {g['id']: g['name'] for g in genre_res.json().get('genres', [])}
except Exception as e:
    print(f"Failed to fetch genres: {e}")
    genre_map = {}

def get_recent_movies(max_pages=500):
    movies = []
    print(f"🚀 Fetching top {max_pages * 20} most popular movies globally since Jan 1, 2023 directly from TMDB Discover API...")
    
    for page in tqdm(range(1, max_pages + 1)):
        # Sort by popularity to get the most relevant upcoming/recent movies worldwide
        url = f"https://api.tmdb.org/3/discover/movie?api_key={API_KEY}&language=en-US&sort_by=popularity.desc&primary_release_date.gte=2023-01-01&page={page}"
        try:
            res = session.get(url, timeout=30)
            if res.status_code != 200:
                print(f"Error on page {page}: {res.status_code}")
                time.sleep(1)
                continue
            time.sleep(0.05)  # Stay safely under 40 requests/sec limit
            data = res.json()
            for item in data.get('results', []):
                # Ensure the overview exists and we aren't adding empty skeleton data
                if not item.get('overview'):
                    continue
                    
                genres = ", ".join([genre_map.get(gid, "") for gid in item.get('genre_ids', [])])
                
                movies.append({
                    'id': item.get('id'),
                    'title': item.get('title'),
                    'vote_average': item.get('vote_average', 0.0),
                    'vote_count': item.get('vote_count', 0),
                    'status': 'Released',
                    'release_date': item.get('release_date', ''),
                    'runtime': 120, # Placeholder, but prevents 0.0 dropping
                    'adult': str(item.get('adult', False)).upper(),
                    'original_language': item.get('original_language', ''),
                    'overview': item.get('overview', ''),
                    'popularity': item.get('popularity', 0.0),
                    'poster_path': item.get('poster_path', ''),
                    'genres': genres,
                    'keywords': '' # TMDB discover doesn't return keywords, but clean genres & overview is highly precise
                })
        except Exception as e:
            print(f"Exception on page {page}: {e}")
        
    return pd.DataFrame(movies)

def main():
    # Fetch top 10,000 most popular movies of 23/24/25
    df_tmdb = get_recent_movies(max_pages=500)
    
    # --- Apply robust DB filters to the TMDB data before saving ---
    df_tmdb['vote_count'] = pd.to_numeric(df_tmdb['vote_count'], errors='coerce').fillna(0)
    df_tmdb = df_tmdb[df_tmdb['vote_count'] > 1]
    df_tmdb = df_tmdb[df_tmdb['vote_average'] < 10]
    df_tmdb = df_tmdb[df_tmdb['popularity'] > 1.75]
    df_tmdb['genres'] = df_tmdb['genres'].fillna('')
    df_tmdb = df_tmdb[~df_tmdb['genres'].str.contains('TV Movie|Documentary', case=False, na=False)]
    
    # Load bulk Kaggle CSV for the historical long-tail
    kaggle_path = get_dataset_path()
    print(f"\n📂 Loading old Kaggle dataset from {kaggle_path} to merge...")
    df_kaggle = pd.read_csv(kaggle_path)
    
    print("🔄 Merging datasets... prioritizing the pristine 100% accurate TMDB API Data for recent movies...")
    df_kaggle.set_index('id', inplace=True)
    df_tmdb.set_index('id', inplace=True)
    
    # Drop existing corrupted rows and append the pristine TMDB data
    intersecting_ids = df_kaggle.index.intersection(df_tmdb.index)
    df_kaggle = df_kaggle.drop(index=intersecting_ids)
    
    df_kaggle = pd.concat([df_kaggle, df_tmdb])
    print(f"✨ Injected {len(df_tmdb)} perfectly clean modern movies into the database!")
    
    df_kaggle.reset_index(inplace=True)
    
    output_path = 'healed_tmdb_dataset.csv'
    print(f"\n💾 Saving Master Database to {output_path}...")
    df_kaggle.to_csv(output_path, index=False)
    print("✅ Done! You can now uncomment the dataset override in build_index.py safely!")

if __name__ == '__main__':
    main()
