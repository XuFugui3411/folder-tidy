"""Per-user Windows install; no admin rights, Python or internet required."""
import base64
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

VERSION = '1.0.0'


def copy_application(source: Path, programs: Path) -> Path:
    if not (source / 'FolderTidy.exe').is_file() or not (source / '_internal').is_dir():
        raise OSError('软件文件不完整，请先完整解压 ZIP，再运行安装到桌面。')
    directory = programs / 'FolderTidy' / 'versions' / (VERSION + '-' + uuid.uuid4().hex[:12])
    directory.parent.mkdir(parents=True, exist_ok=True)
    directory.mkdir()  # a new version never overwrites a running installation
    shutil.copy2(source / 'FolderTidy.exe', directory / 'FolderTidy.exe')
    shutil.copytree(source / '_internal', directory / '_internal')
    for name in ('使用说明.txt', 'THIRD-PARTY-NOTICES.txt'):
        if (source / name).is_file():
            shutil.copy2(source / name, directory / name)
    return directory


def create_shortcut(executable: Path, programs: Path) -> Path:
    # PowerShell receives paths through the environment, never shell interpolation.
    script = r'''
$ErrorActionPreference = 'Stop'
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell
$title = '文件整理助手'
$index = 0
do {
    $name = if ($index -eq 0) { $title + '.lnk' } else { $title + ' (' + $index + ').lnk' }
    $linkPath = Join-Path $desktop $name
    if (!(Test-Path -LiteralPath $linkPath)) { break }
    $old = $shell.CreateShortcut($linkPath)
    $ownedRoot = $env:FOLDER_TIDY_PROGRAMS.TrimEnd('\') + '\FolderTidy\versions\'
    if ($old.TargetPath.StartsWith($ownedRoot, [StringComparison]::OrdinalIgnoreCase) -and
        [IO.Path]::GetFileName($old.TargetPath) -eq 'FolderTidy.exe') { break }
    $index++
} while ($true)
$link = $shell.CreateShortcut($linkPath)
$link.TargetPath = $env:FOLDER_TIDY_EXECUTABLE
$link.WorkingDirectory = [IO.Path]::GetDirectoryName($env:FOLDER_TIDY_EXECUTABLE)
$link.IconLocation = $env:FOLDER_TIDY_EXECUTABLE + ',0'
$link.Description = 'Folder Tidy - 文件整理助手'
$link.Save()
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
Write-Output $linkPath
'''
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    result = subprocess.run(
        [str(powershell), '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
        env={**os.environ, 'FOLDER_TIDY_EXECUTABLE': str(executable), 'FOLDER_TIDY_PROGRAMS': str(programs)},
        capture_output=True, encoding='utf-8', errors='replace',
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=True,
    )
    shortcut = Path(result.stdout.strip())
    if not shortcut.is_file():
        raise OSError('桌面快捷方式创建失败。')
    return shortcut


def run():
    import tkinter as tk
    from tkinter import messagebox
    window = tk.Tk()
    window.title('Folder Tidy · 安装到桌面')
    window.geometry('430x180')
    window.resizable(False, False)
    window.configure(bg='#f6f3ef')
    tk.Label(window, text='安装文件整理助手', font=('Microsoft YaHei UI', 16, 'bold'),
             fg='#73283f', bg='#f6f3ef').pack(anchor='w', padx=26, pady=(26, 12))
    status = tk.StringVar(value='正在复制软件并创建桌面启动器，请稍候…')
    tk.Label(window, textvariable=status, font=('Microsoft YaHei UI', 10),
             fg='#6c5e63', bg='#f6f3ef', wraplength=375, justify='left').pack(anchor='w', padx=26)
    window.update()
    try:
        if os.name != 'nt' or not getattr(sys, 'frozen', False):
            raise OSError('请从 Windows 发布包中运行“安装到桌面.cmd”。')
        programs = Path(os.environ['LOCALAPPDATA']) / 'Programs'
        directory = copy_application(Path(sys.executable).parent, programs)
        shortcut = create_shortcut(directory / 'FolderTidy.exe', programs)
        status.set(f'桌面已创建“{shortcut.stem}”图标。\n安装完成，正在打开软件。')
        window.update()
        subprocess.Popen([str(directory / 'FolderTidy.exe')], cwd=directory,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        window.after(1200, window.quit)
        window.mainloop()
    except Exception as exc:
        messagebox.showerror('安装未完成', f'{exc}\n\n你仍可尝试直接打开解压目录中的 FolderTidy.exe。', parent=window)
        return 1
    finally:
        window.destroy()
    return 0
