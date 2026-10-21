import argparse
from rag.service import answer_drug_question
p=argparse.ArgumentParser()
p.add_argument('question')
a=p.parse_args()
r=answer_drug_question(a.question)
print(r['answer'])
print('\n資料段落：',len(r['sources']))
