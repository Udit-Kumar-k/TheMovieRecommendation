import pickle
import pandas as pd

try:
    with open('index_data.pkl', 'rb') as f:
        data = pickle.load(f)
        df = data['df']
        print("Columns:", df.columns.tolist())
        print("First row:", df.iloc[0].to_dict())
except Exception as e:
    print(e)
