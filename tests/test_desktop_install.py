from pathlib import Path
import tempfile
import unittest

from desktop_install import copy_application


class InstallTests(unittest.TestCase):
    def test_stable_copy_preserves_files_and_uses_new_version_directory(self):
        with tempfile.TemporaryDirectory(prefix='安装 空格 ') as directory:
            root = Path(directory)
            source = root / '解压目录'
            (source / '_internal').mkdir(parents=True)
            (source / 'FolderTidy.exe').write_bytes(b'fake exe fixture')
            (source / '_internal/runtime.dll').write_bytes(b'fixture runtime')
            (source / 'LICENSE').write_text('license fixture', encoding='utf-8')
            (source / 'unrelated.txt').write_bytes(b'not software')
            first = copy_application(source, root / 'Programs')
            second = copy_application(source, root / 'Programs')
            self.assertNotEqual(first, second)
            self.assertEqual((first / 'FolderTidy.exe').read_bytes(), b'fake exe fixture')
            self.assertEqual((second / '_internal/runtime.dll').read_bytes(), b'fixture runtime')
            self.assertEqual((first / 'LICENSE').read_text(encoding='utf-8'), 'license fixture')
            self.assertFalse((first / 'unrelated.txt').exists())
            self.assertTrue((source / 'FolderTidy.exe').exists())

    def test_incomplete_package_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(OSError, '完整解压'):
                copy_application(root, root / 'Programs')


if __name__ == '__main__':
    unittest.main()
