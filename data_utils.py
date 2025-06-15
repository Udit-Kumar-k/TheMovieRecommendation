import os
import kagglehub

def get_dataset_path():
    path = kagglehub.dataset_download("asaniczka/tmdb-movies-dataset-2023-930k-movies")
    return os.path.join(path, "TMDB_movie_dataset_v11.csv")