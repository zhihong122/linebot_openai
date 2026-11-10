"""Exercise actual app.py handlers without booting Flask or external services."""
import ast
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import test_master_roles as fixtures


SOURCE = ast.parse(Path(__file__).with_name('app.py').read_text(encoding='utf-8'))


def load_function(name, namespace):
    node = next(n for n in SOURCE.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'app.py', 'exec'), namespace)
    return namespace[name]


class ImageRoleIntegration(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RoleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.roles = self.fixture.roles

    def test_actual_patient_accessors_use_test_patient_without_real_bindings(self):
        forbidden_db = Mock(side_effect=AssertionError('must not query real patient bindings'))
        namespace = dict(master_roles=self.roles, get_db_connection=forbidden_db)
        self.roles._change(fixtures.OWNER, 'elderly')
        elder = load_function('get_elder_patient_by_line_user_id', namespace)
        self.assertEqual(elder(fixtures.OWNER)['patient_id'], 'test-patient')
        self.roles._change(fixtures.OWNER, 'caregiver')
        for name in ('list_caregiver_patients', 'get_selected_caregiver_patient', 'select_caregiver_patient'):
            load_function(name, namespace)
        self.assertEqual(namespace['list_caregiver_patients'](fixtures.OWNER)[0]['patient_id'], 'test-patient')
        self.assertEqual(namespace['get_selected_caregiver_patient'](fixtures.OWNER)['patient_id'], 'test-patient')
        self.assertEqual(namespace['select_caregiver_patient'](fixtures.OWNER, '1')['patient_id'], 'test-patient')
        with self.assertRaises(RuntimeError):
            namespace['select_caregiver_patient'](fixtures.OWNER, '2')
        forbidden_db.assert_not_called()

    def test_actual_image_handler_records_scans_against_test_patient(self):
        import os
        for role in ('elderly', 'caregiver'):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as tmp:
                self.roles._change(fixtures.OWNER, role)
                cursor = Mock()
                cursor.fetchone.return_value = ('scan-id',)
                connection = Mock()
                connection.cursor.return_value = cursor
                blob = Mock()
                blob.get_message_content.return_value = b'test image bytes'
                client = Mock()
                process = Mock(return_value={'display_text': '測試解析結果'})
                reply = Mock()
                namespace = dict(
                    master_roles=self.roles, os=os, TMP_DIR=tmp,
                    get_user_id=lambda event: fixtures.OWNER,
                    get_user=lambda uid: {'id': 'owner', 'role': role},
                    get_blob_api=lambda: (client, blob),
                    get_operation_state=lambda uid: {'step': 'waiting_elder_prescription_image'} if role == 'elderly' else None,
                    get_db_connection=lambda: connection,
                    _caregiver_user=lambda uid: {'id': 'owner'},
                    clear_operation_state=Mock(), reply_text=reply,
                    process_medication_scan=process, safe_text=lambda text: text,
                )
                for name in ('get_elder_patient_by_line_user_id', 'get_selected_caregiver_patient', 'handle_image_message'):
                    load_function(name, namespace)
                event = self.fixture.event()
                event.message = SimpleNamespace(id='message-' + role)
                namespace['handle_image_message'](event)
                sql, values = cursor.execute.call_args.args
                self.assertIn('INSERT INTO ai_medication_scans', sql)
                self.assertEqual(values[0], 'test-patient')
                self.assertEqual(values[1], 'owner')
                connection.commit.assert_called_once()
                process.assert_called_once_with('scan-id', os.path.join(tmp, 'message-' + role + '.jpg'))
                self.assertIn('測試解析結果', reply.call_args.args[1])
                self.roles._change(fixtures.OWNER)


if __name__ == '__main__':
    unittest.main()
