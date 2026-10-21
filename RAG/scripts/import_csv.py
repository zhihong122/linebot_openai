from rag.ingest import import_csv
import argparse
p=argparse.ArgumentParser()
p.add_argument('csv_path')
p.add_argument('--no-embeddings',action='store_true')
p.add_argument('--limit',type=int)
a=p.parse_args()
print(import_csv(a.csv_path,embeddings=not a.no_embeddings,limit=a.limit))
