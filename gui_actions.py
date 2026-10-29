"""GUI-independent preview gating; no third party dependencies."""
from dataclasses import dataclass
import hashlib
from pathlib import Path

import folder_tidy as tidy


@dataclass
class Preview:
    root: Path
    mode: str
    token: object
    rows: list
    summary: str
    plan: dict | None = None


def stamp(path):
    s = path.lstat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_mode,
            getattr(s, 'st_file_attributes', 0))


def prepare(folder, mode='tidy'):
    if not str(folder).strip():
        raise ValueError('请先选择要整理的文件夹。')
    root = Path(folder).expanduser().resolve(strict=True)
    tidy.safe_directory(root)
    if mode == 'tidy':
        plan = tidy.scan(root)
        token = [(str(s), str(t), stamp(s)) for s, t in plan['moves']]
        token += [('skip', name, reason) for name, reason in plan['skipped']]
        rows = [('待移动', s.name, str(t.relative_to(root))) for s, t in plan['moves']]
        rows += [('跳过', name, reason) for name, reason in plan['skipped']]
        summary = f"扫描 {plan['scanned']} 项 · 计划移动 {len(plan['moves'])} · 跳过 {len(plan['skipped'])}"
        return Preview(root, mode, token, rows, summary, plan)
    if mode != 'undo':
        raise ValueError('未知操作类型')
    found = tidy.latest(root)
    if not found:
        return Preview(root, mode, None, [], '没有可撤销的整理记录。')
    path, record = found
    token = (str(path), hashlib.sha256(path.read_bytes()).hexdigest())
    rows = [('待还原', e['target'], e['source']) for e in reversed(record['entries'])
            if e['status'] in {'pending', 'moved', 'restoring'}]
    return Preview(root, mode, token, rows, f'最近一次整理 · 计划还原 {len(rows)} 个文件')


def apply(preview, emit=print):
    if not preview.rows or (preview.mode == 'tidy' and not preview.plan['moves']):
        raise ValueError('当前没有可执行的文件，请先预览。')
    with tidy.locked(preview.root) as directory:
        current = prepare(preview.root, preview.mode)
        if current.token != preview.token:
            raise ValueError('文件夹内容或操作记录已变化，请重新预览后再执行。')
        if preview.mode == 'undo':
            return tidy.undo(preview.root, True, emit=emit)
        record = tidy.execute(preview.root, directory, preview.plan, emit=emit)
        return all(e['status'] == 'moved' for e in record['entries'])
