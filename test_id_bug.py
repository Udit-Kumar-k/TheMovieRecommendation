import sys, os
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from data_loader import get_data

df, title_to_index, index = get_data()

print("First few raw IDs:")
print(df['id'].head(5))

print("Keys in dict (first 5):")
d = pd.Series(df.index, index=df['id'].astype(str)).to_dict()
keys = list(d.keys())
print(keys[:5])

print("Is '155' in dict?", "155" in d)
print("Is '155.0' in dict?", "155.0" in d)

# Test the type of value in `d`
val = d.get(list(d.keys())[0])
print("Type of dict value:", type(val))
