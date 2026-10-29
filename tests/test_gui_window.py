from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from folder_tidy_gui import TidyApp


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='按钮 验证 ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / '文档.pdf').write_bytes(b'document')
        self.window = tk.Tk()
        self.window.withdraw()
        self.addCleanup(self.window.destroy)
        self.app = TidyApp(self.window)
        self.window.update()

    def wait(self):
        deadline = time.monotonic() + 10
        while self.app.busy:
            self.window.update()
            if time.monotonic() > deadline:
                self.fail('GUI operation timed out')
            time.sleep(0.01)

    def test_folder_dialog_and_button_roundtrip(self):
        self.assertTrue(self.app.apply_button.instate(['disabled']))
        with patch('folder_tidy_gui.filedialog.askdirectory', return_value=str(self.root)):
            self.app.choose_button.invoke()
        self.assertEqual(self.app.folder.get(), str(self.root))
        self.app.preview_button.invoke()
        self.wait()
        self.assertEqual(len(self.app.table.get_children()), 1)
        self.assertTrue(self.app.apply_button.instate(['!disabled']))
        self.assertTrue((self.root / '文档.pdf').exists())
        self.app.apply_button.invoke()
        self.wait()
        self.assertTrue((self.root / 'PDF/文档.pdf').exists())
        self.assertTrue(self.app.apply_button.instate(['disabled']))
        self.app.undo_preview_button.invoke()
        self.wait()
        self.assertTrue(self.app.undo_button.instate(['!disabled']))
        self.app.undo_button.invoke()
        self.wait()
        self.assertEqual((self.root / '文档.pdf').read_bytes(), b'document')

    def test_changing_folder_invalidates_preview(self):
        self.app.folder.set(str(self.root))
        self.app.preview_button.invoke()
        self.wait()
        self.app.folder.set(str(self.root.parent))
        self.assertIsNone(self.app.preview)
        self.assertTrue(self.app.apply_button.instate(['disabled']))
        self.assertEqual(len(self.app.table.get_children()), 0)

    def test_error_does_not_leave_buttons_locked(self):
        self.app.folder.set(str(self.root / 'missing'))
        with patch('folder_tidy_gui.messagebox.showerror') as error:
            self.app.preview_button.invoke()
            self.wait()
        error.assert_called_once()
        self.assertTrue(self.app.preview_button.instate(['!disabled']))
        self.assertTrue(self.app.apply_button.instate(['disabled']))


if __name__ == '__main__':
    unittest.main()
