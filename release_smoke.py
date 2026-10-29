"""Frozen runtime verification using disposable fixtures only."""
import json
from pathlib import Path
import tempfile


def run(report):
    import tkinter as tk
    from folder_tidy_gui import TidyApp
    import gui_actions
    checks = []
    with tempfile.TemporaryDirectory(prefix='FolderTidy 中文 验证 ') as directory:
        root = Path(directory)
        (root / '报告 文档.pdf').write_bytes(b'original pdf')
        (root / 'PDF').mkdir()
        (root / 'PDF/报告 文档.pdf').write_bytes(b'old pdf')
        preview = gui_actions.prepare(root)
        assert not (root / '.folder-tidy').exists()
        checks.append('preview_no_writes')
        assert gui_actions.apply(preview, lambda _: None)
        assert (root / 'PDF/报告 文档 (1).pdf').read_bytes() == b'original pdf'
        assert (root / 'PDF/报告 文档.pdf').read_bytes() == b'old pdf'
        checks.append('unicode_spaces_collision_move')
        (root / '新增.png').write_bytes(b'new image')
        assert gui_actions.apply(gui_actions.prepare(root, 'undo'), lambda _: None)
        assert (root / '报告 文档.pdf').read_bytes() == b'original pdf'
        assert (root / '新增.png').read_bytes() == b'new image'
        checks.append('undo_preserves_new_files')
        window = tk.Tk()
        window.withdraw()
        try:
            app = TidyApp(window)
            app.folder.set(str(root))
            window.update()
            assert app.apply_button.instate(['disabled'])
            checks.append('tkinter_window_and_theme')
        finally:
            window.destroy()
    Path(report).write_text(json.dumps({'ok': True, 'checks': checks}, ensure_ascii=False, indent=2), encoding='utf-8')
