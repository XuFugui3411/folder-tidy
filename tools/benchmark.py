"""Measure real hash/journal work without changing the file-safety algorithm.

Standard library only. All files are generated in fresh temporary subdirectories;
no user folder is scanned. Fixture creation/validation/cleanup are not timed.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import folder_tidy as tidy

CASES = [('small-100', 100, 4096), ('small-500', 500, 4096),
         ('small-1000', 1000, 4096), ('large-4x128MiB', 4, 128 * 1024 * 1024)]


@contextmanager
def measure():
    values = dict(identity_calls=0, hash_read_bytes=0, hash_seconds=0.0,
                  journal_writes=0, journal_bytes=0, journal_seconds=0.0)
    identity, save = tidy.identity, tidy.save

    def measured_identity(path):
        started = time.perf_counter()
        result = identity(path)
        values['hash_seconds'] += time.perf_counter() - started
        values['identity_calls'] += 1
        values['hash_read_bytes'] += result['size']
        return result

    def measured_save(path, record):
        started = time.perf_counter()
        save(path, record)
        values['journal_seconds'] += time.perf_counter() - started
        values['journal_writes'] += 1
        values['journal_bytes'] += path.stat().st_size

    with patch.object(tidy, 'identity', measured_identity), patch.object(tidy, 'save', measured_save):
        started = time.perf_counter()
        yield values
        values['wall_seconds'] = time.perf_counter() - started


def fixtures(root, count, size):
    block = hashlib.sha256(b'folder-tidy-benchmark-fixture').digest() * 32768
    for index in range(count):
        with (root / f'file-{index:05d}.pdf').open('xb') as stream:
            remaining = size
            while remaining:
                length = min(remaining, len(block))
                stream.write(block[:length])
                remaining -= length


def run_case(workdir, name, count, size, trial):
    with tempfile.TemporaryDirectory(prefix='trial-', dir=workdir) as directory:
        root = Path(directory).resolve()
        if root.parent != workdir:
            raise RuntimeError('Temporary path escaped the requested benchmark workspace')
        fixtures(root, count, size)
        originals = {p.name: p.stat().st_ino for p in root.iterdir()}
        started = time.perf_counter()
        plan = tidy.scan(root)
        scan_seconds = time.perf_counter() - started
        assert plan['scanned'] == count and len(plan['moves']) == count
        with measure() as execution:
            with tidy.locked(root) as state:
                record = tidy.execute(root, state, plan, emit=lambda _: None)
        assert len(record['entries']) == count and all(e['status'] == 'moved' for e in record['entries'])
        assert execution['identity_calls'] == 4 * count
        assert execution['hash_read_bytes'] == 4 * count * size
        assert execution['journal_writes'] == 2 * count + 1
        final_journal_bytes = next((root / tidy.STATE).glob('*.json')).stat().st_size
        with measure() as undo:
            with tidy.locked(root):
                assert tidy.undo(root, True, emit=lambda _: None)
        assert undo['identity_calls'] == 4 * count and undo['journal_writes'] == 2 * count
        for filename, inode in originals.items():
            path = root / filename
            assert path.stat().st_ino == inode and path.stat().st_size == size
        assert not list((root / 'PDF').iterdir())
        return dict(case=name, trial=trial, files=count, bytes_per_file=size,
                    payload_bytes=count * size, scan_seconds=scan_seconds,
                    execution=execution, undo=undo, final_journal_bytes=final_journal_bytes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True, help='Volume to measure; only generated trial-* children are touched')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--environment', type=Path, help='Optional JSON with public CPU/storage metadata')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--case', choices=[x[0] for x in CASES], action='append')
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be at least 1')
    workdir = args.workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data = dict(measured_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                python=platform.python_version(), platform=platform.platform(),
                machine=platform.machine(), core_sha256=hashlib.sha256((ROOT / 'folder_tidy.py').read_bytes()).hexdigest(),
                repeats=args.repeats, cache_policy='Freshly written fixtures; OS cache is not flushed. Not a cold-disk benchmark.',
                instrumentation='Real identity/save calls wrapped for timing; byte counts are logical full-file reads and UTF-8 JSON file lengths, not physical device I/O.',
                environment=json.loads(args.environment.read_text(encoding='utf-8-sig')) if args.environment else {}, results=[])
    for name, count, size in CASES:
        if args.case and name not in args.case:
            continue
        for trial in range(1, args.repeats + 1):
            result = run_case(workdir, name, count, size, trial)
            data['results'].append(result)
            args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f"{name} #{trial}: execute={result['execution']['wall_seconds']:.3f}s undo={result['undo']['wall_seconds']:.3f}s", flush=True)
    data['summary'] = []
    for name, _, _ in CASES:
        rows = [r for r in data['results'] if r['case'] == name]
        if rows:
            data['summary'].append(dict(case=name, execute_median=statistics.median(r['execution']['wall_seconds'] for r in rows),
                                        undo_median=statistics.median(r['undo']['wall_seconds'] for r in rows)))
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
