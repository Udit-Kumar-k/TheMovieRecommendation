import numpy as np
import faiss

idx = np.int64(0)
d = 64
index = faiss.IndexFlatL2(d)
index.add(np.random.random((10, d)).astype('float32'))

try:
    index.reconstruct(idx)
    print("reconstruct(numpy.int64) OK")
except Exception as e:
    print("reconstruct(numpy.int64) ERROR:", type(e), e)

try:
    index.reconstruct(int(idx))
    print("reconstruct(int) OK")
except Exception as e:
    print("reconstruct(int) ERROR:", type(e), e)
