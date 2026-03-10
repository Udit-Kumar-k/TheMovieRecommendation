import pandas as pd
import requests
import os
from dotenv import load_dotenv
from tqdm import tqdm
import time
from data_utils import get_dataset_path

# Load environment variable
load_dotenv()
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

if not TMDB_API_KEY:
    print("❌ ERROR: TMDB_API_KEY not found in .env file.")
    exit()

print("✅ Loaded TMDB API Key.")

# Load raw dataset
csv_file = get_dataset_path()
print(f"Loading base dataset: {csv_file}")
df = pd.read_csv(csv_file)

# Pre-filter logic matching build_index.py (Don't waste API calls on movies we would drop anyway!)
initial_len = len(df)
df = df[df['popularity'] > 1.75]

# Safely parse votes and release dates
from datetime import datetime
current_year = datetime.now().year
df['release_year'] = pd.to_datetime(df['release_date'], errors='coerce').dt.year
df['vote_count'] = pd.to_numeric(df['vote_count'], errors='coerce').fillna(0)
df = df[df['vote_count'] > 1]
df = df[df['vote_average'] < 10]

has_ratings = df['vote_average'] > 0
is_recent = df['release_year'] >= (current_year - 2)
df = df[has_ratings | is_recent]
df = df.drop(columns=['release_year'])

print(f"✅ Filtered base dataset from {initial_len} to {len(df)} eligible movies.")

# Ensure columns exist and fill NaNs
df['overview'] = df['overview'].fillna('')
df['keywords'] = df['keywords'].fillna('')

# Identify "Skeleton" movies
# Condition 1: Overview is extremely short or empty
missing_overview = df['overview'].str.len() < 20
# Condition 2: Keywords are empty
missing_keywords = df['keywords'].str.strip() == ''

skeleton_mask = missing_overview | missing_keywords
skeleton_df = df[skeleton_mask]

print(f"🔍 Found {len(skeleton_df)} 'Skeleton' movies missing critical overview or keyword data.")

if skeleton_df.empty:
    print("✅ No skeleton movies found! Saving healed dataset directly.")
    df.to_csv('healed_tmdb_dataset.csv', index=False)
    exit()

# Time to heal them
success_count = 0
fail_count = 0

print("🚀 Starting TMDB API Data Fetch sequentially to respect strict rate limits...")

# Iterate through skeleton rows
for idx, row in tqdm(skeleton_df.iterrows(), total=len(skeleton_df), desc="Healing Skeletons"):
    movie_id = row['id']
    
    # Safety Check: If it's not a valid number, skip
    try:
        tmdb_id = int(float(movie_id))
    except (ValueError, TypeError):
        fail_count += 1
        continue
    
    # Hit TMDB API (append_to_response=keywords gets both in one call!)
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=keywords&language=en-US"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract new overview
            new_overview = data.get('overview', '')
            if new_overview and len(new_overview) > 10:
                df.at[idx, 'overview'] = new_overview
            
            # Extract new keywords
            keywords_data = data.get('keywords', {}).get('keywords', [])
            if not keywords_data:
                # Fallback for old TMDB response format
                keywords_data = data.get('keywords', {}).get('results', [])
                
            if keywords_data:
                keyword_names = [k.get('name', '') for k in keywords_data if k.get('name')]
                new_keywords_str = ", ".join(keyword_names)
                df.at[idx, 'keywords'] = new_keywords_str
            
            success_count += 1
        elif response.status_code == 429:
            # We hit a rate limit even while sequential! Wait a bit longer.
            time.sleep(2.0)
            fail_count += 1 # We'll just count it as fail and move on for now
        else:
            # e.g., 404 Not Found
            fail_count += 1
            
    except requests.exceptions.RequestException as e:
        # Network errors
        fail_count += 1
        continue
        
    # Respect the 40 requests/second limit strictly
    time.sleep(0.12)

print("\n--- Healing Complete ---")
print(f"✅ Successfully healed: {success_count} movies.")
print(f"⚠️ Failed/Not Found: {fail_count} movies.")

print("💾 Saving updated dataset to 'healed_tmdb_dataset.csv'...")
df.to_csv('healed_tmdb_dataset.csv', index=False)
print("🎉 Done! You can now run build_index.py or update_index.py")
