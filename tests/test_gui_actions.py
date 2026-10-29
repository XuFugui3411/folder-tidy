from pathlib import Path
import tempfile
import unittest

import gui_actions as actions
import folder_tidy as tidy


class ActionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='窗口 测试 ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / '报告 文档.pdf').write_bytes(b'pdf data')

    def test_prepare_has_no_writes(self):
        preview = actions.prepare(self.root)
        self.assertEqual(len(preview.rows), 1)
        self.assertFalse((self.root / tidy.STATE).exists())
        self.assertTrue((self.root / '报告 文档.pdf').exists())

    def test_apply_then_undo(self):
        preview = actions.prepare(self.root)
        self.assertTrue(actions.apply(preview, lambda _: None))
        undo = actions.prepare(self.root, 'undo')
        self.assertEqual(len(undo.rows), 1)
        self.assertTrue(actions.apply(undo, lambda _: None))
        self.assertEqual((self.root / '报告 文档.pdf').read_bytes(), b'pdf data')

    def test_new_file_after_preview_requires_new_preview(self):
        preview = actions.prepare(self.root)
        (self.root / '后来新增.png').write_bytes(b'image')
        with self.assertRaisesRegex(ValueError, '重新预览'):
            actions.apply(preview)
        self.assertTrue((self.root / '报告 文档.pdf').exists())
        self.assertTrue((self.root / '后来新增.png').exists())

    def test_changed_source_after_preview_requires_new_preview(self):
        preview = actions.prepare(self.root)
        (self.root / '报告 文档.pdf').write_bytes(b'edited file')
        with self.assertRaisesRegex(ValueError, '重新预览'):
            actions.apply(preview)

    def test_new_collision_after_preview_requires_new_preview(self):
        preview = actions.prepare(self.root)
        (self.root / 'PDF').mkdir()
        (self.root / 'PDF/报告 文档.pdf').write_bytes(b'existing')
        with self.assertRaisesRegex(ValueError, '重新预览'):
            actions.apply(preview)
        self.assertEqual((self.root / 'PDF/报告 文档.pdf').read_bytes(), b'existing')

    def test_history_changed_after_undo_preview_requires_new_preview(self):
        actions.apply(actions.prepare(self.root), lambda _: None)
        undo = actions.prepare(self.root, 'undo')
        (self.root / 'new.png').write_bytes(b'image')
        actions.apply(actions.prepare(self.root), lambda _: None)
        with self.assertRaisesRegex(ValueError, '重新预览'):
            actions.apply(undo)

    def test_new_original_during_undo_kept(self):
        actions.apply(actions.prepare(self.root), lambda _: None)
        undo = actions.prepare(self.root, 'undo')
        (self.root / '报告 文档.pdf').write_bytes(b'new file')
        self.assertFalse(actions.apply(undo, lambda _: None))
        self.assertEqual((self.root / '报告 文档.pdf').read_bytes(), b'new file')
        self.assertEqual((self.root / 'PDF/报告 文档.pdf').read_bytes(), b'pdf data')

    def test_blank_path_and_empty_undo(self):
        with self.assertRaises(ValueError):
            actions.prepare('')
        undo = actions.prepare(self.root, 'undo')
        self.assertEqual(undo.rows, [])
        with self.assertRaises(ValueError):
            actions.apply(undo)


if __name__ == '__main__':
    unittest.main()
