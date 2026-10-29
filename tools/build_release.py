"""Build and verify a Windows portable ZIP plus a clean source ZIP."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from desktop_install import VERSION


def make_icon(path):
    size = 32
    pixels = bytearray()
    for y in reversed(range(size)):
        for x in range(size):
            r, g, b, a = (115, 40, 63, 255)
            if ((6 <= x < 15 and 8 <= y < 11) or (6 <= x < 26 and 11 <= y < 14)
                    or (6 <= x < 9 and 13 <= y < 25) or (23 <= x < 26 and 13 <= y < 25)
                    or (6 <= x < 26 and 22 <= y < 25)):
                r, g, b = (246, 233, 221)
            pixels.extend((b, g, r, a))
    dib = struct.pack('<IiiHHIIiiII', 40, size, size * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0)
    data = dib + pixels + bytes(size * 4)
    path.write_bytes(struct.pack('<HHH', 0, 1, 1) + struct.pack('<BBBBHHII', size, size, 0, 0, 1, 32, len(data), 22) + data)


def zip_folder(folder, output):
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                archive.write(path, str(Path(folder.name) / path.relative_to(folder)))
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None


def build():
    if sys.platform != 'win32' or struct.calcsize('P') != 8:
        raise SystemExit('Build on 64-bit Windows with 64-bit Python.')
    output = ROOT / 'releases'
    output.mkdir(exist_ok=True)
    work = ROOT / 'build'
    work.mkdir(exist_ok=True)
    icon = work / 'folder-tidy.ico'
    make_icon(icon)
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--windowed',
        '--noupx', '--name', 'FolderTidy', '--icon', str(icon),
        '--distpath', str(ROOT / 'dist'), '--workpath', str(work / 'pyinstaller'),
        '--specpath', str(work), str(ROOT / 'folder_tidy_gui.py'),
    ], cwd=ROOT, check=True)
    folder = ROOT / 'dist' / 'FolderTidy'
    shutil.copy2(ROOT / 'docs' / '使用说明.txt', folder / '使用说明.txt')
    # Batch launcher is ASCII; it invokes the bundled runtime, not system Python.
    (folder / '安装到桌面.cmd').write_bytes(
        b'@echo off\r\nstart "" "%~dp0FolderTidy.exe" --install-desktop\r\n')
    notices = ['Folder Tidy third-party notices', '',
               'Python runtime: https://docs.python.org/3/license.html',
               'PyInstaller bootloader: GPL with distribution exception.',
               'https://pyinstaller.org/en/stable/license.html', '']
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        raise RuntimeError('Python license text was not found')
    notices.extend(['--- Python license ---', python_license.read_text(encoding='utf-8')])
    distribution = importlib.metadata.distribution('pyinstaller')
    for item in distribution.files:
        if str(item).endswith('COPYING.txt'):
            notices.extend(['--- PyInstaller license ---', distribution.locate_file(item).read_text(encoding='utf-8')])
    for pattern in ('**/license.terms', '**/LICENSE.terms'):
        for path in folder.glob(pattern):
            notices.extend(['--- ' + str(path.relative_to(folder)) + ' ---', path.read_text(encoding='utf-8', errors='replace')])
    (folder / 'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(notices), encoding='utf-8')
    report = work / 'frozen-smoke.json'
    report.unlink(missing_ok=True)
    result = subprocess.run([str(folder / 'FolderTidy.exe'), '--self-test', str(report)], cwd=work, timeout=90)
    if result.returncode != 0 or not report.is_file() or not json.loads(report.read_text(encoding='utf-8'))['ok']:
        raise RuntimeError('Frozen EXE smoke test failed')
    print(report.read_text(encoding='utf-8'))
    portable = output / f'FolderTidy-{VERSION}-windows-x64.zip'
    zip_folder(folder, portable)
    source = output / f'folder-tidy-{VERSION}-source.zip'
    with zipfile.ZipFile(source, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.iterdir()):
            if path.is_file() and (path.suffix in {'.py', '.pyw', '.cmd'} or path.name in {'README.md', '.gitignore', 'requirements-build.txt'}):
                archive.write(path, str(Path('folder-tidy') / path.name))
        for name in ('tests', 'tools', 'docs', '.github'):
            for path in sorted((ROOT / name).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts:
                    archive.write(path, str(Path('folder-tidy') / path.relative_to(ROOT)))
    checksums = '\n'.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name for p in (portable, source)) + '\n'
    (output / 'SHA256SUMS.txt').write_text(checksums, encoding='utf-8')
    print(checksums)


if __name__ == '__main__':
    build()
