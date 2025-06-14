import pandas as pd
import os
import kagglehub

# ---------------- Load Dataset ---------------- #
dataset_path = kagglehub.dataset_download("alanvourch/tmdb-movies-daily-updates")
csv_file = os.path.join(dataset_path, "TMDB_all_movies.csv")

# Try reading the file with fallback engine and skip bad rows
try:
    df = pd.read_csv(csv_file, encoding='utf-8-sig', engine='python', on_bad_lines='skip')
except Exception as e:
    print(f"❌ Error loading CSV: {e}")
    exit()

# ---------------- Validate Columns ---------------- #
expected_columns = ['keywords', 'overview', 'genres']
for col in expected_columns:
    if col not in df.columns:
        print(f"⚠️ Column missing: {col}. Filling with empty string.")
        df[col] = ''

# ---------------- Confirm Columns ---------------- #
print("✅ Final columns in DataFrame:")
print(df.columns.tolist())

