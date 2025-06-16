import pandas as pd
import os
import kagglehub

path = kagglehub.dataset_download("asaniczka/tmdb-movies-dataset-2023-930k-movies")

csv_file = os.path.join(path, "TMDB_movie_dataset_v11.csv")
df = pd.read_csv(csv_file, engine='python')

print("\n🧾 Columns in the dataset:")
print(df.columns.tolist())

if 'genres' in df.columns:
    # Drop NaN values in the genre column
    genres_series = df['genres'].dropna()

    # Split the genre strings and flatten the list
    all_genres = set()
    for genre_str in genres_series:
        for genre in genre_str.split(','):
            all_genres.add(genre.strip())

    print("\n🎬 Unique genres in the dataset:")
    for genre in sorted(all_genres):
        print("-", genre)
else:
    print("❌ 'genres' column not found in the dataset.")

#Unique genres in the dataset:
#- Action
#- Adventure
#- Animation
#- Comedy
#- Crime
#- Documentary
#- Drama
#- Family
#- Fantasy
#- History
#- Horror
#- Music
#- Mystery
#- Romance
#- Science Fiction
#- TV Movie
#- Thriller
#- War
#- Western