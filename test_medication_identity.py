import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

from medication_identity import extract_identity, resolve_medication, strengths


ASCOFEN = dict(drug_id=10, source_id=2121, license_number='衛署藥製字第057798號',
               name_zh='「生達」炎立消膜衣錠100毫克',
               name_en='Ascofen F.C. Tablets 100mg "Standard" (Aceclofenac)',
               ingredient='每錠Aceclofenac 100mg。')
OTHER = dict(drug_id=20, source_id=1297, license_number='衛部藥製字第058361號',
             name_zh='剋炎痛膜衣錠100毫克', name_en='Aclopain F.C. Tablets 100mg',
             ingredient='每錠Aceclofenac 100 mg。')
PHOTO = '''商品名：Ascofen FC Tab 100mg
中文名：炎立消膜衣錠100毫克
學名：Aceclofenac
含量：100mg
劑型：膜衣錠
廠牌：生達
許可證字號：未標示'''


class IdentityTests(unittest.TestCase):
    def resolve(self, block=PHOTO, candidates=None):
        return resolve_medication(extract_identity(block), candidates or [ASCOFEN, OTHER])

    def test_hospital_names_match_official_product(self):
        result = self.resolve()
        self.assertEqual(result['drug_id'], 10)
        self.assertEqual(result['source_id'], 2121)
        self.assertIn('ingredient', result['matched_fields'])

    def test_english_abbreviations_without_chinese(self):
        self.assertEqual(self.resolve('Ascofen FC Tab 100mg')['drug_id'], 10)

    def test_chinese_without_manufacturer_prefix(self):
        self.assertEqual(self.resolve('商品名：未標示\n中文名：炎立消膜衣錠100毫克')['drug_id'], 10)

    def test_wrong_strength_is_rejected(self):
        self.assertEqual(self.resolve(PHOTO.replace('100', '200'))['status'], 'not_found')

    def test_wrong_ingredient_is_rejected(self):
        self.assertEqual(self.resolve(PHOTO.replace('學名：Aceclofenac', '學名：Acetaminophen'))['status'], 'not_found')

    def test_misspelled_ingredient_is_not_silently_corrected(self):
        self.assertEqual(self.resolve(PHOTO.replace('學名：Aceclofenac', '學名：Acelofenac'))['status'], 'not_found')

    def test_wrong_manufacturer_is_rejected(self):
        self.assertEqual(self.resolve(PHOTO.replace('廠牌：生達', '廠牌：其他'))['status'], 'not_found')

    def test_conflicting_product_names_are_rejected(self):
        self.assertEqual(self.resolve(PHOTO.replace('Ascofen', 'Aclopain'))['status'], 'not_found')

    def test_generic_and_dose_are_not_a_product_identity(self):
        result = self.resolve('學名：Aceclofenac\n含量：100mg\n劑型：膜衣錠')
        self.assertEqual(result['status'], 'not_found')

    def test_ambiguity_is_detected_before_chunk_limit(self):
        duplicate = dict(ASCOFEN, drug_id=30, license_number='另一許可證')
        self.assertEqual(self.resolve(candidates=[ASCOFEN, duplicate])['status'], 'ambiguous')

    def test_license_disambiguates_and_still_checks_dose(self):
        duplicate = dict(ASCOFEN, drug_id=30, license_number='另一許可證')
        block = PHOTO.replace('許可證字號：未標示', '許可證字號：衛署藥製字第057798號')
        self.assertEqual(self.resolve(block, [ASCOFEN, duplicate])['drug_id'], 10)
        self.assertEqual(self.resolve(block.replace('100', '200'))['status'], 'not_found')

    def test_extended_release_not_equivalent_to_regular(self):
        self.assertEqual(self.resolve('Ascofen SR Tab 100mg')['status'], 'not_found')

    def test_capsule_not_equivalent_to_tablet(self):
        self.assertEqual(self.resolve('Ascofen Capsule 100mg')['status'], 'not_found')

    def test_different_tablet_coatings_not_equivalent(self):
        self.assertEqual(self.resolve('Ascofen SC Tab 100mg')['status'], 'not_found')

    def test_concentrations_and_units(self):
        self.assertEqual(strengths('0.1 g'), strengths('100mg'))
        self.assertEqual(strengths('1000 mcg'), strengths('1mg'))
        self.assertEqual(strengths('100mg/5mL'), strengths('20mg/mL'))
        self.assertNotEqual(strengths('100mg/5mL'), strengths('100mg'))

    def test_duplicate_identity_labels_are_not_merged(self):
        block = PHOTO + '\n商品名：Aclopain FC Tab 100mg'
        self.assertEqual(self.resolve(block)['status'], 'not_found')

    def test_legacy_brand_plus_generic(self):
        self.assertEqual(self.resolve('Ascofen FC Tab 100mg; Aceclofenac 100mg')['drug_id'], 10)


class RetrievalTests(unittest.TestCase):
    def lookup(self, candidates):
        path = Path(__file__).parent / 'RAG/rag/service.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in ('search_medication_sources', '_public_row')]
        calls = []
        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def execute(self, sql, params=None): calls.append((sql, params))
            def fetchall(self):
                if len(calls) == 1:
                    return [tuple(row.get(k) for k in ('drug_id','source_id','license_number','name_zh','name_en','ingredient')) for row in candidates]
                return [(10, 2121, ASCOFEN['license_number'], ASCOFEN['name_zh'], ASCOFEN['name_en'], '副作用', '測試證據', '測試PDF', 0)]
        class Connection:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def cursor(self): return Cursor()
        ns = {'connection':Connection}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
        return ns['search_medication_sources'](extract_identity(PHOTO), top_k=1), calls

    def test_reads_existing_columns_then_only_matched_product_chunks(self):
        result, calls = self.lookup([ASCOFEN, OTHER])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][1], (10, 1))
        self.assertEqual(result['sources'][0]['drug_id'], 10)
        for sql, _ in calls:
            self.assertTrue(sql.strip().startswith('SELECT'))

    def test_ambiguous_products_never_retrieve_chunks(self):
        result, calls = self.lookup([ASCOFEN, dict(ASCOFEN, drug_id=30)])
        self.assertEqual(len(calls), 1)
        self.assertEqual(result['sources'], [])
        self.assertEqual(result['identity_match']['status'], 'ambiguous')


if __name__ == '__main__':
    unittest.main()

