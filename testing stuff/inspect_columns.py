import pandas as pd
import os
import kagglehub

path = kagglehub.dataset_download("asaniczka/tmdb-movies-dataset-2023-930k-movies")

csv_file = os.path.join(path, "TMDB_movie_dataset_v11.csv")
df = pd.read_csv(csv_file, engine='python')

print("\n🧾 Columns in the dataset:")
print(df.columns.tolist())