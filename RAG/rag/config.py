import os
from dotenv import load_dotenv
load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL', '')
EMBEDDING_MODEL = os.getenv('RAG_EMBEDDING_MODEL', 'text-embedding-3-small')
CHAT_MODEL = os.getenv('RAG_CHAT_MODEL', 'gpt-oss:20b')
CHAT_BASE_URL = os.getenv('RAG_CHAT_BASE_URL', 'http://localhost:11434/v1').rstrip('/')
CHAT_API_KEY = os.getenv('RAG_CHAT_API_KEY', 'ollama')
CHAT_TIMEOUT = float(os.getenv('RAG_CHAT_TIMEOUT', '180'))
CF_ACCESS_CLIENT_ID = os.getenv('CF_ACCESS_CLIENT_ID', '').strip()
CF_ACCESS_CLIENT_SECRET = os.getenv('CF_ACCESS_CLIENT_SECRET', '').strip()
MAX_EVIDENCE_CHARS = max(1000, int(os.getenv('RAG_MAX_EVIDENCE_CHARS', '11000')))

EMBEDDING_DIM = int(os.getenv('RAG_EMBEDDING_DIM', '1536'))
USE_EMBEDDINGS = os.getenv('RAG_ENABLE_EMBEDDINGS', 'false').lower() == 'true'
TOP_K = max(1, min(int(os.getenv('RAG_TOP_K', '8')), 15))
