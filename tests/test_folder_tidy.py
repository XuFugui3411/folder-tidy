import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import folder_tidy as tidy


class TidyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='整理 测试 ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def put(self, name, content=b'original'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def run_cli(self, *options):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return tidy.main([str(self.root), *options])

    def apply(self):
        self.assertEqual(self.run_cli('--execute'), 0)

    def restore(self):
        self.assertEqual(self.run_cli('--undo', '--execute'), 0)

    def test_preview_has_no_writes(self):
        self.put('中文 文件.PDF')
        before = list(self.root.iterdir())
        self.assertEqual(self.run_cli(), 0)
        self.assertEqual(before, list(self.root.iterdir()))

    def test_unicode_spaces_and_roundtrip(self):
        self.put('中文 文件.PDF', b'pdf')
        self.put('holiday photo.PNG', b'image')
        self.apply()
        self.assertEqual((self.root / 'PDF/中文 文件.PDF').read_bytes(), b'pdf')
        self.assertEqual((self.root / 'Images/holiday photo.PNG').read_bytes(), b'image')
        self.restore()
        self.assertEqual((self.root / '中文 文件.PDF').read_bytes(), b'pdf')
        self.assertEqual((self.root / 'holiday photo.PNG').read_bytes(), b'image')

    def test_collision_preserves_both_and_numbered_names(self):
        self.put('PDF/a.pdf', b'old')
        self.put('PDF/a (1).pdf', b'older')
        self.put('a.pdf', b'new')
        self.apply()
        self.assertEqual((self.root / 'PDF/a (2).pdf').read_bytes(), b'new')
        self.restore()
        self.assertEqual((self.root / 'PDF/a.pdf').read_bytes(), b'old')
        self.assertEqual((self.root / 'PDF/a (1).pdf').read_bytes(), b'older')
        self.assertEqual((self.root / 'a.pdf').read_bytes(), b'new')

    def test_late_collision_cannot_overwrite(self):
        source = self.put('a.pdf')
        target = self.put('PDF/a.pdf', b'new arrival')
        with self.assertRaises(FileExistsError):
            tidy.transfer(source, target, tidy.identity(source))
        self.assertEqual(source.read_bytes(), b'original')
        self.assertEqual(target.read_bytes(), b'new arrival')

    def test_second_run_no_nesting_and_noop_does_not_hide_history(self):
        self.put('a.pdf')
        self.apply()
        self.apply()
        self.assertFalse((self.root / 'PDF/PDF').exists())
        self.restore()
        self.assertEqual((self.root / 'a.pdf').read_bytes(), b'original')

    def test_new_files_survive_undo_and_retry(self):
        self.put('a.pdf')
        self.apply()
        self.put('a.pdf', b'new root file')
        self.put('PDF/new.pdf', b'new category file')
        self.assertEqual(self.run_cli('--undo', '--execute'), 1)
        self.assertEqual((self.root / 'a.pdf').read_bytes(), b'new root file')
        self.assertEqual((self.root / 'PDF/a.pdf').read_bytes(), b'original')
        self.assertEqual((self.root / 'PDF/new.pdf').read_bytes(), b'new category file')
        (self.root / 'a.pdf').rename(self.root / 'new file.pdf')
        self.restore()
        self.assertEqual((self.root / 'PDF/new.pdf').read_bytes(), b'new category file')

    def test_modified_destination_is_not_restored(self):
        self.put('a.pdf')
        self.apply()
        target = self.root / 'PDF/a.pdf'
        target.write_bytes(b'modified')
        self.assertEqual(self.run_cli('--undo', '--execute'), 1)
        self.assertEqual(target.read_bytes(), b'modified')
        self.assertFalse((self.root / 'a.pdf').exists())

    def test_replaced_destination_even_identical_bytes_is_preserved(self):
        self.put('a.pdf')
        self.apply()
        target = self.root / 'PDF/a.pdf'
        target.rename(self.root / 'saved.pdf')  # keep old inode alive
        self.put('PDF/a.pdf')
        self.assertEqual(self.run_cli('--undo', '--execute'), 1)
        self.assertTrue(target.exists())

    def test_undo_preview_does_not_write(self):
        self.put('a.pdf')
        self.apply()
        log, _ = tidy.latest(self.root)
        before = log.read_bytes()
        self.assertEqual(self.run_cli('--undo'), 0)
        self.assertEqual(log.read_bytes(), before)
        self.assertTrue((self.root / 'PDF/a.pdf').exists())

    def test_failure_continues_to_other_files(self):
        self.put('a.pdf')
        self.put('b.pdf', b'other')
        original = tidy.transfer

        def fail_one(source, target, expected):
            if source.name == 'a.pdf':
                raise PermissionError('file is in use')
            original(source, target, expected)

        with patch.object(tidy, 'transfer', side_effect=fail_one):
            self.assertEqual(self.run_cli('--execute'), 1)
        self.assertEqual((self.root / 'a.pdf').read_bytes(), b'original')
        self.assertEqual((self.root / 'PDF/b.pdf').read_bytes(), b'other')
        self.restore()

    def test_unlink_failure_rolls_back_extra_link(self):
        source = self.put('a.pdf')
        target = self.root / 'b.pdf'
        original = Path.unlink

        def fail_source(path, *args, **kwargs):
            if path == source:
                raise PermissionError('source busy')
            return original(path, *args, **kwargs)

        with patch.object(Path, 'unlink', fail_source):
            with self.assertRaises(PermissionError):
                tidy.transfer(source, target, tidy.identity(source))
        self.assertTrue(source.exists())
        self.assertFalse(target.exists())

    def test_logs_are_written_before_move(self):
        self.put('a.pdf')
        with patch.object(tidy, 'save', side_effect=OSError('disk full')):
            self.assertEqual(self.run_cli('--execute'), 1)
        self.assertEqual((self.root / 'a.pdf').read_bytes(), b'original')

    def test_fsync_failure_leaves_source_and_no_partial_journal(self):
        self.put('a.pdf')
        with patch.object(tidy.os, 'fsync', side_effect=OSError('disk full')):
            self.assertEqual(self.run_cli('--execute'), 1)
        self.assertEqual((self.root / 'a.pdf').read_bytes(), b'original')
        self.assertEqual(list((self.root / tidy.STATE).glob('*.tmp')), [])
        self.apply()  # failed journal write must not block future retries

    def test_undo_log_failure_stops_before_restoring_any_file(self):
        self.put('a.pdf')
        self.put('b.pdf')
        self.apply()
        with patch.object(tidy, 'save', side_effect=OSError('disk full')):
            self.assertEqual(self.run_cli('--undo', '--execute'), 1)
        self.assertFalse((self.root / 'a.pdf').exists())
        self.assertFalse((self.root / 'b.pdf').exists())
        self.restore()

    def test_interrupted_undo_can_retry(self):
        self.put('a.pdf')
        self.apply()
        real_save = tidy.save

        def save_until_undone(path, record):
            if any(e['status'] == 'undone' for e in record['entries']):
                raise OSError('disk full after restore')
            real_save(path, record)

        with patch.object(tidy, 'save', side_effect=save_until_undone):
            self.assertEqual(self.run_cli('--undo', '--execute'), 1)
        self.assertEqual((self.root / 'a.pdf').read_bytes(), b'original')
        self.restore()
        self.assertIsNone(tidy.latest(self.root))

    def test_unavailable_hardlinks_do_not_remove_sources(self):
        self.put('a.pdf')
        with patch.object(tidy.os, 'link', side_effect=OSError('hardlinks unsupported')):
            self.assertEqual(self.run_cli('--execute'), 1)
        self.assertEqual((self.root / 'a.pdf').read_bytes(), b'original')
        self.assertFalse((self.root / 'PDF/a.pdf').exists())

    def test_post_move_log_failure_can_be_recovered(self):
        self.put('a.pdf')
        real_save = tidy.save

        def save_until_moved(path, record):
            if any(e['status'] == 'moved' for e in record['entries']):
                raise OSError('disk full after move')
            real_save(path, record)

        with patch.object(tidy, 'save', side_effect=save_until_moved):
            self.assertEqual(self.run_cli('--execute'), 1)
        self.assertEqual(tidy.latest(self.root)[1]['entries'][0]['status'], 'pending')
        self.restore()
        self.assertEqual((self.root / 'a.pdf').read_bytes(), b'original')

    def test_interrupted_extra_link_recovery(self):
        self.put('a.pdf')

        def interrupted(source, target, expected):
            os.link(source, target)
            raise KeyboardInterrupt()

        with patch.object(tidy, 'transfer', side_effect=interrupted):
            self.assertEqual(self.run_cli('--execute'), 130)
        self.restore()
        self.assertEqual((self.root / 'a.pdf').read_bytes(), b'original')
        self.assertFalse((self.root / 'PDF/a.pdf').exists())

    def test_history_lifo(self):
        self.put('a.pdf')
        self.apply()
        self.put('b.png')
        self.apply()
        self.restore()
        self.assertTrue((self.root / 'b.png').exists())
        self.assertTrue((self.root / 'PDF/a.pdf').exists())
        self.restore()
        self.assertTrue((self.root / 'a.pdf').exists())

    def test_statistics_and_skips(self):
        self.put('a.pdf')
        self.put('untitled', b'unknown')
        self.put('half.crdownload')
        (self.root / 'nested').mkdir()
        plan = tidy.scan(self.root)
        self.assertEqual(plan['scanned'], 4)
        self.assertEqual(len(plan['moves']), 2)
        self.assertEqual(len(plan['skipped']), 2)
        self.assertEqual(plan['moves'][1][1].parent.name, 'Others')

    def test_category_blocked_by_file(self):
        self.put('PDF')
        self.put('a.pdf')
        plan = tidy.scan(self.root)
        self.assertTrue(any(name == 'a.pdf' for name, _ in plan['skipped']))

    def test_concurrent_execution_rejected(self):
        with tidy.locked(self.root):
            self.assertEqual(self.run_cli('--execute'), 1)

    def test_symlinks_not_followed(self):
        source = self.put('real.pdf')
        try:
            (self.root / 'link.pdf').symlink_to(source)
            (self.root / 'Images').symlink_to(self.root / 'outside', target_is_directory=True)
        except OSError:
            self.skipTest('OS does not permit symlinks')
        self.put('photo.png')
        plan = tidy.scan(self.root)
        self.assertIn('link.pdf', [name for name, _ in plan['skipped']])
        self.assertIn('photo.png', [name for name, _ in plan['skipped']])

    def test_unsafe_journal_path_rejected(self):
        self.put('a.pdf')
        self.apply()
        log, record = tidy.latest(self.root)
        record['entries'][0]['source'] = '../outside.pdf'
        tidy.save(log, record)
        self.assertEqual(self.run_cli('--undo', '--execute'), 1)
        self.assertTrue((self.root / 'PDF/a.pdf').exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows junctions')
    def test_windows_junction_category_not_followed(self):
        outside = self.root / 'outside'
        outside.mkdir()
        junction = self.root / 'Images'
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)],
                                capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.addCleanup(junction.rmdir)
        self.put('photo.png')
        self.apply()
        self.assertTrue((self.root / 'photo.png').exists())
        self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows sharing semantics')
    def test_real_windows_busy_file_continues(self):
        import ctypes
        from ctypes import wintypes
        source = self.put('a.pdf')
        self.put('b.pdf')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(source), 0x80000000, 0, None, 3, 0, None)
        self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
        try:
            self.assertEqual(self.run_cli('--execute'), 1)
            self.assertTrue(source.exists())
            self.assertTrue((self.root / 'PDF/b.pdf').exists())
        finally:
            kernel.CloseHandle(handle)

    def test_command_line_entrypoint(self):
        self.put('测试 文档.pdf')
        result = subprocess.run([sys.executable, str(Path(tidy.__file__)), str(self.root)],
                                capture_output=True, encoding='utf-8',
                                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('计划移动 1', result.stdout)
        self.assertTrue((self.root / '测试 文档.pdf').exists())


if __name__ == '__main__':
    unittest.main()
