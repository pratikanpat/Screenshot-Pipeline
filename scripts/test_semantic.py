import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
db = chromadb.PersistentClient(path='data/chroma')
col = db.get_collection('screenshots')
print('ChromaDB vectors stored:', col.count())
print()

from backend.pipeline.embeddings import semantic_search

queries = [
    'payment confirmation phonepe gpay paytm',
    'instagram chat direct message',
    'group photo people together',
    'invoice receipt bill gst',
    'profile picture circular avatar',
    'instagram post feed photo',
    'whatsapp chat message',
]

for q in queries:
    results = semantic_search(q, n_results=3)
    print('Query:', repr(q))
    for r in results:
        fname = r['metadata'].get('filename', '?')
        score = round(1 - r['distance'], 3)
        print('  id=' + str(r['image_id']) + '  score=' + str(score) + '  file=' + fname)
    print()
