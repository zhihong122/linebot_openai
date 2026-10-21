from pathlib import Path
from rag.db import connection
with connection() as conn:
    conn.execute(Path('rag/schema.sql').read_text(encoding='utf-8'))
print('資料表建立完成')
