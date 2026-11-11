import ast
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('medication_rag', Path(__file__).with_name('medication_rag.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ScanRAGTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'RAG_ENABLED':'true', 'RAG_SHOW_TIMING':'true'})
        self.env.start()
        os.environ.pop('RAG_MEDICATION_ENABLED', None)
        self.text = '・藥名＋含量：Example 500mg tab\n・每次量：1 粒\n・可能副作用：未標示\n・警語：已標示警語\n・QR Code（掃描後連結）：https://example.com'
        self.row = dict(drug_id=1, name_zh='', name_en='Example', section='副作用', content='測試來源', license_number='TEST', source='測試資料庫')
        self.service = types.ModuleType('RAG.rag.service')
        self.service.search_drugs = lambda *a, **kw: [self.row]
        response = types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='{"supplements":[{"field":"可能副作用","text":"測試補充","citations":[1]},{"field":"每次量","text":"不可補充","citations":[1]},{"field":"警語","text":"不可覆蓋","citations":[1]}]}'))])
        self.service.chat_client = lambda: types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **kw: response)))
        package = types.ModuleType('RAG.rag')
        package.config = types.SimpleNamespace(MAX_EVIDENCE_CHARS=10000, CHAT_MODEL='test')
        self.modules = patch.dict(sys.modules, {'RAG':types.ModuleType('RAG'), 'RAG.rag':package, 'RAG.rag.service':self.service})
        self.modules.start()
    def tearDown(self):
        self.modules.stop()
        self.env.stop()
    def run_scan(self):
        return mod.enrich_medication_result({'display_text':self.text, 'qr':{'value':'https://example.com'}})
    def test_success_preserves_ocr_and_puts_timing_last(self):
        result = self.run_scan()
        self.assertTrue(result['display_text'].startswith(self.text))
        self.assertIn('測試補充 [1]', result['display_text'])
        self.assertNotIn('不可補充', result['display_text'])
        self.assertNotIn('不可覆蓋', result['display_text'])
        self.assertTrue(result['display_text'].splitlines()[-1].startswith('RAG 處理耗時：'))
        self.assertEqual(result['rag']['status'], 'completed')
    def test_disabled_is_not_reported_as_execution(self):
        os.environ['RAG_ENABLED'] = 'false'
        result = self.run_scan()
        self.assertEqual(result['rag']['status'], 'disabled')
        self.assertIn('未執行（未啟用）', result['display_text'])
    def test_not_found(self):
        self.service.search_drugs = lambda *a, **kw: []
        self.assertEqual(self.run_scan()['rag']['status'], 'not_found')
    def test_ambiguous_and_fuzzy_match_are_rejected(self):
        self.service.search_drugs = lambda *a, **kw: [self.row, dict(self.row, drug_id=2)]
        self.assertEqual(self.run_scan()['rag']['status'], 'ambiguous')
        self.service.search_drugs = lambda *a, **kw: [dict(self.row, name_en='Other')]
        self.assertEqual(self.run_scan()['rag']['status'], 'ambiguous')
    def test_failure_preserves_ocr(self):
        def fail(*a, **kw):
            raise RuntimeError('database unavailable')
        self.service.search_drugs = fail
        with self.assertLogs(mod.logger, level='ERROR'):
            result = self.run_scan()
        self.assertEqual(result['rag']['status'], 'failed')
        self.assertTrue(result['display_text'].startswith(self.text))
        self.assertTrue(result['display_text'].endswith('（失敗）'))
    def test_timing_can_be_hidden(self):
        os.environ['RAG_SHOW_TIMING'] = 'false'
        self.assertNotIn('RAG 處理耗時', self.run_scan()['display_text'])
    def test_background_push_keeps_timing_after_long_text(self):
        tree = ast.parse(Path(__file__).with_name('app.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'start_medication_scan_reply')
        events = []
        text = '辨識結果' * 3000 + '\nRAG 處理耗時：1.23 秒'
        api = types.SimpleNamespace(close=lambda: events.append('closed'))
        messaging = types.SimpleNamespace(push_message=lambda req: events.append(req))
        class ImmediateThread:
            def __init__(self, target, **kw): self.target = target
            def start(self): self.target()
        ns = dict(_rag_slots=types.SimpleNamespace(acquire=lambda **kw:True, release=lambda:None),
                  process_medication_scan=lambda *a: {'display_text':text},
                  get_messaging_api=lambda:(api, messaging),
                  PushMessageRequest=lambda **kw:kw, TextMessage=lambda **kw:kw,
                  reply_text=lambda *a:events.append('ack'), threading=types.SimpleNamespace(Thread=ImmediateThread))
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<push>', 'exec'), ns)
        event = types.SimpleNamespace(source=types.SimpleNamespace(user_id='user'), reply_token='token')
        ns['start_medication_scan_reply'](event, 123, 'test.jpg', '完成\n')
        self.assertEqual(events[0], 'ack')
        pushes = [e for e in events if isinstance(e, dict)]
        joined = ''.join(m['text'] for p in pushes for m in p['messages'])
        self.assertEqual(joined, '完成\n' + text)
        self.assertTrue(joined.endswith('RAG 處理耗時：1.23 秒'))
        self.assertTrue(all(len(m['text']) <= 4000 for p in pushes for m in p['messages']))
    def test_actual_process_enriches_before_save(self):
        tree = ast.parse(Path(__file__).with_name('app.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'process_medication_scan')
        saved = []
        ns = dict(os=os, openai_client=None, analyze_medication_image=lambda **kw: {'display_text':self.text}, enrich_medication_result=mod.enrich_medication_result, save_medication_scan_analysis=lambda scan_id, **kw:saved.append(kw))
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<scan>', 'exec'), ns)
        result = ns['process_medication_scan'](123, 'test.jpg')
        self.assertIn('RAG 處理耗時', result['display_text'])
        self.assertEqual(saved[0]['result'], result)

if __name__ == '__main__':
    unittest.main()

