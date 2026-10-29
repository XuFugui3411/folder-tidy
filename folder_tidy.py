"""Preview-first, non-recursive file organiser. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import uuid

STATE = '.folder-tidy'
TYPES = {
    'PDF': 'pdf',
    'Images': 'jpg jpeg png gif webp bmp tif tiff svg heic avif ico',
    'Archives': 'zip rar 7z tar gz bz2 xz tgz',
    'Documents': 'doc docx xls xlsx ppt pptx txt md rtf csv odt ods epub',
    'Audio': 'mp3 wav flac aac ogg m4a',
    'Video': 'mp4 mkv avi mov webm m4v wmv',
    'Code': 'py js ts html css json xml yaml yml toml sql c cpp h java rs go',
}
EXTENSIONS = {ext: category for category, exts in TYPES.items() for ext in exts.split()}
CATEGORIES = set(TYPES) | {'Others'}
TEMP_EXTENSIONS = {'.tmp', '.part', '.crdownload', '.download'}


def is_link(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, 'st_file_attributes', 0) & 0x400)  # Windows reparse points/junctions


def regular(path: Path) -> None:
    if is_link(path) or not stat.S_ISREG(path.lstat().st_mode):
        raise OSError(f'不是普通文件或是链接：{path}')


def identity(path: Path) -> dict:
    regular(path)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if fields(before) != fields(after):
        raise OSError(f'读取期间文件发生变化：{path}')
    return dict(dev=after.st_dev, ino=after.st_ino, size=after.st_size,
                mtime=after.st_mtime_ns, sha256=digest.hexdigest())


def same_file(path: Path, expected: dict) -> bool:
    return identity(path) == expected


def safe_directory(path: Path, create: bool = False) -> None:
    if create:
        path.mkdir(exist_ok=True)
    if is_link(path) or not path.is_dir():
        raise OSError(f'目录不可用或是链接：{path}')


def choose_name(path: Path, reserved: set[str]) -> Path:
    candidate = path
    number = 1
    while os.path.lexists(candidate) or str(candidate).casefold() in reserved:
        candidate = path.with_name(f'{path.stem} ({number}){path.suffix}')
        number += 1
    reserved.add(str(candidate).casefold())
    return candidate


def scan(root: Path) -> dict:
    result = dict(scanned=0, moves=[], skipped=[])
    reserved: set[str] = set()
    for source in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
        if source.name == STATE:
            continue
        result['scanned'] += 1
        try:
            regular(source)
            if source.suffix.lower() in TEMP_EXTENSIONS:
                raise OSError('临时/未下载完成文件')
            category = EXTENSIONS.get(source.suffix.lower().lstrip('.'), 'Others')
            directory = root / category
            if os.path.lexists(directory):
                safe_directory(directory)
            target = choose_name(directory / source.name, reserved)
            result['moves'].append((source, target))
        except OSError as exc:
            result['skipped'].append((source.name, str(exc)))
    return result


def show_plan(root: Path, plan: dict) -> None:
    for source, target in plan['moves']:
        print(f'  移动 {source.name!r} -> {str(target.relative_to(root))!r}')
    for name, reason in plan['skipped']:
        print(f'  跳过 {name!r}：{reason}')
    print(f"扫描 {plan['scanned']} 项 | 计划移动 {len(plan['moves'])} | 跳过 {len(plan['skipped'])}")


@contextmanager
def locked(root: Path):
    directory = root / STATE
    safe_directory(directory, create=True)
    path = directory / 'lock'
    if os.path.lexists(path):
        regular(path)
    with path.open('a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise OSError('已有 folder-tidy 在操作此目录，请稍后重试') from exc
        try:
            yield directory
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def save(path: Path, record: dict) -> None:
    """Atomic journal replacement; failure stops the batch instead of losing history."""
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def transfer(source: Path, target: Path, expected: dict) -> None:
    """Hard link creation is atomic and refuses overwrite, unlike Unix rename.

    Both locations are on the same filesystem. No copy/delete fallback: on an
    unsupported filesystem it is safer to report failure and leave the source.
    """
    if not same_file(source, expected):
        raise OSError('文件自计划生成后已改变')
    os.link(source, target, follow_symlinks=False)
    try:
        if not same_file(target, expected) or not same_file(source, expected):
            raise OSError('移动期间文件发生变化')
        source.unlink()
    except BaseException:
        # Only remove the extra link we created; never a replacement file.
        try:
            current = target.lstat()
            if (current.st_dev, current.st_ino) == (expected['dev'], expected['ino']):
                target.unlink()
        except OSError:
            pass  # pending journal enables a later undo/recovery
        raise


def execute(root: Path, directory: Path, plan: dict, emit=print) -> dict:
    record = dict(version=1, root=str(root), created=datetime.now(timezone.utc).isoformat(),
                  id=uuid.uuid4().hex, entries=[], scanned=plan['scanned'],
                  skipped=len(plan['skipped']), skipped_files=plan['skipped'])
    path = directory / (record['created'].replace(':', '-') + '-' + record['id'] + '.json')
    save(path, record)
    for source, proposed in plan['moves']:
        entry = dict(source=source.name, target=str(proposed.relative_to(root)), status='failed')
        record['entries'].append(entry)
        try:
            safe_directory(proposed.parent, create=True)
            target = choose_name(proposed, set())  # collisions may have appeared since preview
            entry.update(target=str(target.relative_to(root)), identity=identity(source), status='pending')
        except OSError as exc:
            entry['error'] = str(exc)
            save(path, record)
            emit(f'  失败 {source.name!r}：{exc}')
            continue
        save(path, record)  # write-ahead: do not move unless durable intent exists
        try:
            transfer(source, target, entry['identity'])
            entry['status'] = 'moved'
            emit(f'  完成 {source.name!r} -> {entry["target"]!r}')
        except OSError as exc:
            # Keep pending if an extra link survived cleanup.
            entry['status'] = 'pending' if os.path.lexists(target) else 'failed'
            entry['error'] = str(exc)
            emit(f'  失败 {source.name!r}：{exc}')
        save(path, record)
    emit(f"已移动 {sum(e['status'] == 'moved' for e in record['entries'])} | "
          f"失败 {sum(e['status'] != 'moved' for e in record['entries'])}")
    emit(f'操作记录：{path}')
    return record


def latest(root: Path) -> tuple[Path, dict] | None:
    directory = root / STATE
    if not os.path.lexists(directory):
        return None
    safe_directory(directory)
    for path in sorted(directory.glob('*.json'), reverse=True):
        regular(path)
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('version') != 1 or record.get('root') != str(root):
            raise ValueError(f'操作记录版本或根路径不匹配：{path}')
        if any(e['status'] in {'pending', 'moved', 'restoring'} for e in record['entries']):
            return path, record
    return None


def entry_paths(root: Path, entry: dict) -> tuple[Path, Path]:
    source, target = Path(entry['source']), Path(entry['target'])
    if (source.is_absolute() or len(source.parts) != 1 or source.name in {'.', '..', STATE}
            or target.is_absolute() or len(target.parts) != 2
            or target.parts[0] not in CATEGORIES or target.name in {'.', '..'}
            or ':' in str(source) or ':' in str(target)):
        raise ValueError('操作记录含不安全的路径')
    safe_directory(root / target.parent)
    return root / source, root / target


def undo(root: Path, apply: bool, emit=print) -> bool:
    found = latest(root)
    if not found:
        emit('没有可撤销的整理记录。')
        return True
    path, record = found
    emit(f"撤销操作：{record['created']}")
    restored = failed = planned = 0
    for entry in reversed(record['entries']):
        if entry['status'] not in {'pending', 'moved', 'restoring'}:
            continue
        planned += 1
        try:
            source, target = entry_paths(root, entry)
            expected = entry['identity']
            target_exists = os.path.lexists(target)
            source_exists = os.path.lexists(source)
            if target_exists and not same_file(target, expected):
                raise OSError('归类后的文件已修改或被替换，保留现场')
            if source_exists and not same_file(source, expected):
                raise OSError('原位置已有其他文件，保留双方')
            if not target_exists and not source_exists:
                raise OSError('文件已丢失或被外部移动')
            emit(f'  还原 {entry["target"]!r} -> {entry["source"]!r}')
        except OSError as exc:
            failed += 1
            emit(f'  冲突/失败 {entry["source"]!r}：{exc}')
            continue
        if apply:
            entry['status'] = 'restoring'
            save(path, record)  # journal errors abort the batch
            try:
                if source_exists:
                    if target_exists:
                        target.unlink()  # interrupted link/unlink: original already exists
                else:
                    transfer(target, source, expected)
                entry['status'] = 'undone'
                entry.pop('error', None)
                restored += 1
            except OSError as exc:
                failed += 1
                entry['error'] = str(exc)
                emit(f'  冲突/失败 {entry["source"]!r}：{exc}')
            save(path, record)
    emit(f'计划还原 {planned} | 已还原 {restored} | 冲突/失败 {failed}')
    if not apply:
        emit('仅预览；加 --execute 才会撤销。')
    return failed == 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='folder-tidy：默认预览，安全归类与撤销（仅扫描第一层）')
    parser.add_argument('folder', type=Path, help='待整理的文件夹；含空格时请加引号')
    parser.add_argument('--execute', action='store_true', help='实际执行移动或撤销')
    parser.add_argument('--undo', action='store_true', help='撤销最近一次尚未完全撤销的整理，默认预览')
    args = parser.parse_args(argv)
    try:
        root = args.folder.expanduser().resolve(strict=True)
        safe_directory(root)
        if args.execute:
            with locked(root) as directory:
                if args.undo:
                    return 0 if undo(root, True) else 1
                plan = scan(root)
                show_plan(root, plan)
                record = execute(root, directory, plan)
                return int(any(e['status'] != 'moved' for e in record['entries']))
        if args.undo:
            return 0 if undo(root, False) else 1
        show_plan(root, scan(root))
        print('仅预览；加 --execute 才会移动文件。')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\n操作中断；已落盘的记录可用 --undo 检查和恢复。', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
