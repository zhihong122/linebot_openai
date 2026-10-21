"""Drug RAG: exact drug identification + PostgreSQL text/vector retrieval + grounded response."""
import os
import re
from .db import connection
from . import config

SECTION_KEYWORDS = {
 '藥物交互作用':['一起吃','一起用','併用','交互','衝突','相互作用','搭配'],
 '禁忌':['禁忌','不能吃','不可以吃','不適合','過敏','禁用'],
 '副作用':['副作用','不良反應','不舒服','頭暈'],
 '用法用量':['用法','用量','一天幾次','怎麼吃','怎麼用','劑量'],
 '食物／酒精注意':['酒精','喝酒','食物','飯前','飯後','葡萄柚'],
 '適應症':['治療','功效','用途','什麼病','適應症'],
 '成分':['成分','學名','含有'],
 '警語／注意事項':['注意','孕婦','哺乳','小孩','腎臟','肝臟']
}

def openai_client():
    """Optional separate OpenAI embedding client (gpt-oss itself does not embed)."""
    if not os.getenv('OPENAI_API_KEY'):
        return None
    from openai import OpenAI
    return OpenAI(api_key=os.environ['OPENAI_API_KEY'], timeout=35)


def chat_client():
    """OpenAI-compatible gpt-oss-20b server (Ollama/local/cloud)."""
    from openai import OpenAI
    headers = {}
    if bool(config.CF_ACCESS_CLIENT_ID) != bool(config.CF_ACCESS_CLIENT_SECRET):
        raise ValueError('CF_ACCESS_CLIENT_ID 和 CF_ACCESS_CLIENT_SECRET 必須同時設定')
    if config.CF_ACCESS_CLIENT_ID:
        if not config.CHAT_BASE_URL.startswith('https://'):
            raise ValueError('Cloudflare Access 連線必須使用 HTTPS URL')
        headers = {
            'CF-Access-Client-Id': config.CF_ACCESS_CLIENT_ID,
            'CF-Access-Client-Secret': config.CF_ACCESS_CLIENT_SECRET,
        }
    return OpenAI(
        default_headers=headers,
        base_url=config.CHAT_BASE_URL,
        api_key=config.CHAT_API_KEY,
        timeout=config.CHAT_TIMEOUT,
        max_retries=1,
    )

def wanted_sections(question):
    matched=[sec for sec,words in SECTION_KEYWORDS.items() if any(w in question for w in words)]
    return matched or []

def _public_row(r):
    return {'drug_id':r[0],'source_id':r[1],'license_number':r[2], 'name_zh':r[3],
            'name_en':r[4], 'section':r[5], 'content':r[6], 'source':r[7],
            'score':round(float(r[8]),4)}

def search_drugs(question, top_k=None, use_vectors=True):
    """Full-text + trigram drug matching, optional pgvector. Never requires API key."""
    question=(question or '').strip()
    if not question: return []
    top_k=top_k or config.TOP_K
    sections=wanted_sections(question)
    client=openai_client() if use_vectors and config.USE_EMBEDDINGS else None
    vector=None
    if client:
        try:
            emb=client.embeddings.create(model=config.EMBEDDING_MODEL,input=question,dimensions=config.EMBEDDING_DIM)
            vector=emb.data[0].embedding
        except Exception:
            vector=None
    with connection() as conn, conn.cursor() as cur:
        # Candidate drugs by name/license/ingredient; conservatively use char bigrams for Chinese.
        cur.execute('''
            SELECT d.id FROM rag_drugs d WHERE d.is_active AND (
              position(lower(coalesce(d.name_zh,'')) in lower(%s))>0 AND length(coalesce(d.name_zh,''))>=2
              OR position(lower(coalesce(d.name_en,'')) in lower(%s))>0 AND length(coalesce(d.name_en,''))>=3
              OR position(lower(coalesce(d.license_number,'')) in lower(%s))>0 AND length(coalesce(d.license_number,''))>=5
              OR similarity(coalesce(d.name_zh,''),%s)>0.48
              OR similarity(coalesce(d.name_en,''),%s)>0.55
            ) LIMIT 24''',(question,question,question,question,question))
        ids=[r[0] for r in cur.fetchall()]
        if ids:
            # Once a drug is identified, restrict to it rather than leaking evidence from other drugs.
            from psycopg.types.json import Jsonb
            cur.execute('''
              SELECT d.id,d.source_id,d.license_number,d.name_zh,d.name_en,c.section,c.content,d.source,
                (CASE WHEN c.section=ANY(%s) THEN 30 ELSE 0 END
                 + CASE WHEN position(lower(coalesce(d.name_zh,'')) in lower(%s))>0 THEN 20 ELSE 0 END
                 + ts_rank(to_tsvector('simple',c.content),plainto_tsquery('simple',%s))*5
                 + CASE WHEN %s IS NOT NULL AND c.embedding IS NOT NULL THEN 1 ELSE 0 END) AS score
              FROM rag_chunks c JOIN rag_drugs d ON d.id=c.drug_id
              WHERE d.id=ANY(%s) AND d.is_active
              ORDER BY score DESC,c.chunk_order ASC LIMIT %s
            ''',(sections,question,question,vector,ids,top_k))
        elif vector is not None:
            cur.execute('''
              SELECT d.id,d.source_id,d.license_number,d.name_zh,d.name_en,c.section,c.content,d.source,
                (1-(c.embedding <=> %s::vector)) AS score
              FROM rag_chunks c JOIN rag_drugs d ON d.id=c.drug_id
              WHERE d.is_active AND c.embedding IS NOT NULL
              ORDER BY c.embedding <=> %s::vector LIMIT %s
            ''',(vector,vector,top_k))
        else:
            # pg_trgm fallback for Chinese multi-character questions, without vector API.
            cur.execute('''
              SELECT d.id,d.source_id,d.license_number,d.name_zh,d.name_en,c.section,c.content,d.source,
                  greatest(similarity(c.content,%s), similarity(coalesce(d.name_zh,''),%s)) AS score
              FROM rag_chunks c JOIN rag_drugs d ON d.id=c.drug_id
              WHERE d.is_active
              ORDER BY score DESC LIMIT %s
            ''',(question,question,top_k))
        return [_public_row(row) for row in cur.fetchall()]

def answer_drug_question(question, top_k=None):
    results=search_drugs(question,top_k=top_k)
    if not results:
        return {'answer':'目前知識庫沒有找到足夠的藥品資料，請提供藥品完整名稱或許可證字號。','sources':[]}
    evidence='\n\n'.join(f"[{i}] {r['name_zh'] or r['name_en']}｜{r['section']}｜許可證：{r['license_number'] or '未提供'}｜資料來源：{r['source'] or '未提供'}\n{r['content']}" for i,r in enumerate(results,1))
    evidence=evidence[:config.MAX_EVIDENCE_CHARS]
    client=chat_client()
    system='''你是藥品仿單查詢輔助系統。只能用提供的仿單段落作答，不可補造劑量、禁忌、交互作用或來源。每一個醫藥事實請標註引用編號如 [1]。不要把「-」或無記載解釋成「安全、沒有交互作用」。如果問題涉及兩藥併用，而證據不足以確認兩者交互作用，請直接說明無法確認，建議藥師或醫師核對完整處方。遇到疑似嚴重不良反應提醒立即就醫。回答使用繁體中文，條理清楚，簡短，不給個人化處方或停藥指示。'''
    response=client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=[{'role':'system','content':system},
                  {'role':'user','content':f'問題：{question}\n\n證據：\n{evidence}'}],
        temperature=0.2,
    )
    return {'answer':response.choices[0].message.content,'sources':results}
