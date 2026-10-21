"""CSV 22欄導入；ID 是固定 upsert key，不使用許可證做唯一鍵。"""
import csv
import hashlib
import json
import re
from pathlib import Path
from .db import connection
from . import config

FIELDS = {
    '許可證字號':'license_number','中文品名':'name_zh','英文品名':'name_en',
    '成分':'ingredient','適應症':'indications','用法用量':'dosage',
    '禁忌':'contraindications','藥物交互作用':'interactions',
    '食物／酒精注意':'food_alcohol','副作用':'side_effects',
    '警語／注意事項':'warnings','來源類型':'source_type','來源':'source',
    '本機檔名':'local_filename','辨識方式':'recognition_method',
    '完整 OCR 文字':'raw_ocr_text','修正後完整文字':'corrected_full_text',
    '審核狀態':'original_review_status','審核備註':'review_notes',
    '建立時間':'original_created_at','更新時間':'original_updated_at',
}
SECTIONS = [('成分','ingredient'), ('適應症','indications'), ('用法用量','dosage'),
            ('禁忌','contraindications'),('藥物交互作用','interactions'),
            ('食物／酒精注意','food_alcohol'),('副作用','side_effects'),
            ('警語／注意事項','warnings')]

def clean(v):
    v = (v or '').strip()
    return None if v.lower() in ('', '-', '－', '—', 'nan', 'null', 'none') else v

def make_chunks(data, max_chars=850, overlap=90):
    """按欄位語意分段，超長章節以字符切分並保留少量重疊。"""
    name = data.get('name_zh') or data.get('name_en') or f"紀錄 {data['source_id']}"
    prefix = f"藥品：{name}；英文：{data.get('name_en') or '未提供'}；許可證：{data.get('license_number') or '未提供'}\n"
    out=[]
    for section, key in SECTIONS:
        value = data.get(key)
        if not value: continue
        start=0; idx=0
        while start < len(value):
            if start+max_chars < len(value):
                cut = value.rfind('\n', start + max_chars//2, start+max_chars)
                end = cut if cut > start else start + max_chars
            else: end=len(value)
            piece=value[start:end].strip()
            if piece: out.append((section,idx,prefix+f'章節：{section}\n'+piece))
            if end>=len(value): break
            start=max(start+1,end-overlap);idx+=1
    # 若結構化章節全部缺失，回退修正文本（避免重複嵌入完整 OCR）
    if not out and data.get('corrected_full_text'):
        raw=data['corrected_full_text']
        for i in range(0,len(raw),750):
            out.append(('完整仿單',i//750,prefix+raw[i:i+850]))
    return out

def embed_texts(texts, client):
    response=client.embeddings.create(model=config.EMBEDDING_MODEL,input=texts,dimensions=config.EMBEDDING_DIM)
    result=sorted(response.data,key=lambda x:x.index)
    return [r.embedding for r in result]

def import_csv(csv_path, embeddings=True, limit=None):
    from .service import openai_client
    client = openai_client() if embeddings and config.USE_EMBEDDINGS else None
    if embeddings and config.USE_EMBEDDINGS and client is None:
        raise RuntimeError('已啟用 Embedding，請設定 OPENAI_API_KEY；或使用 --no-embeddings。')
    counts={'inserted_or_updated':0,'unchanged':0,'chunks':0,'rows':0}
    with open(csv_path,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        missing=set(['ID',*FIELDS])-set(reader.fieldnames or [])
        if missing: raise ValueError(f'CSV 缺少欄位：{sorted(missing)}')
        with connection() as conn:
            for row in reader:
                if limit is not None and counts['rows'] >= limit:break
                counts['rows']+=1
                source_id=int(row['ID'])
                data={'source_id':source_id,**{v:clean(row[k]) for k,v in FIELDS.items()}}
                digest=hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                with conn.cursor() as cur:
                    cur.execute('SELECT id,content_hash FROM rag_drugs WHERE source_id=%s',(source_id,))
                    old=cur.fetchone()
                    if old and old[1]==digest:
                        counts['unchanged']+=1;continue
                    keys=[*data,'content_hash']
                    from psycopg import sql
                    stmt=sql.SQL('INSERT INTO rag_drugs ({cols}) VALUES ({values}) ON CONFLICT (source_id) DO UPDATE SET {updates}, imported_at=now() RETURNING id').format(
                        cols=sql.SQL(',').join(map(sql.Identifier,keys)),
                        values=sql.SQL(',').join([sql.Placeholder()]*len(keys)),
                        updates=sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(k),sql.Identifier(k)) for k in keys if k!='source_id'))
                    cur.execute(stmt,[*data.values(),digest]);drug_id=cur.fetchone()[0]
                    cur.execute('DELETE FROM rag_chunks WHERE drug_id=%s',(drug_id,))
                    chunks=make_chunks(data)
                    vectors=[]
                    if client:
                        for start in range(0,len(chunks),64):
                            vectors.extend(embed_texts([x[2] for x in chunks[start:start+64]],client))
                    for i,(section,order,content) in enumerate(chunks):
                        cur.execute('INSERT INTO rag_chunks (drug_id,section,chunk_order,content,embedding,embedding_model) VALUES (%s,%s,%s,%s,%s,%s)',
                          (drug_id,section,order,content,vectors[i] if vectors else None,config.EMBEDDING_MODEL if vectors else None))
                    counts['chunks']+=len(chunks)
                conn.commit()
                counts['inserted_or_updated']+=1
                if counts['rows'] % 50==0:print(f"已處理 {counts['rows']} 筆，新增/更新 {counts['inserted_or_updated']} 筆")
    return counts

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('csv_path',type=Path)
    p.add_argument('--no-embeddings',action='store_true')
    p.add_argument('--limit',type=int)
    args=p.parse_args()
    print(import_csv(args.csv_path,embeddings=not args.no_embeddings,limit=args.limit))
