"""Create the RAG schema before registering pgvector types on normal connections."""
from pathlib import Path
import psycopg
from rag import config

if not config.DATABASE_URL:
    raise RuntimeError('請先設定 RAG_DATABASE_URL 或 DATABASE_URL')
schema = Path(__file__).resolve().parents[1] / 'rag' / 'schema.sql'
with psycopg.connect(config.DATABASE_URL, connect_timeout=15) as conn:
    conn.execute(schema.read_text(encoding='utf-8'))
print('資料表建立完成')
