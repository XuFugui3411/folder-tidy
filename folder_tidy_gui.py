"""Local Tk desktop application. Run with pythonw for a console-free window."""
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import gui_actions
import gui_theme


class TidyApp:
    def __init__(self, window):
        self.window = window
        self.preview = None
        self.busy = False
        self.events = queue.Queue()
        gui_theme.build(self, window)
        window.protocol('WM_DELETE_WINDOW', self.close)
        self.buttons()
        self.poll_id = self.window.after(80, self.poll)
        self.window.bind('<Destroy>', self.on_destroy, add='+')

    def buttons(self):
        for control in self.controls:
            control.configure(state='disabled' if self.busy else 'normal')
        can_tidy = self.preview and self.preview.mode == 'tidy' and self.preview.plan['moves']
        can_undo = self.preview and self.preview.mode == 'undo' and self.preview.rows
        self.apply_button.configure(state='normal' if not self.busy and can_tidy else 'disabled')
        self.undo_button.configure(state='normal' if not self.busy and can_undo else 'disabled')
        if self.preview and self.preview.mode == 'undo':
            self.apply_button.pack_forget()
            self.undo_button.pack(side='right')
        else:
            self.undo_button.pack_forget()
            self.apply_button.pack(side='right')

    def invalidate(self, *_):
        self.preview = None
        self.table.delete(*self.table.get_children())
        self.summary.set('请点击“预览整理”或“预览撤销”')
        self.status.set('路径已更新；尚未移动任何文件')
        self.list_title.set('整理预览')
        gui_theme.update_stats(self)
        gui_theme.show_empty(self, '文件夹已选择', '点击下方「预览整理」，查看文件将被移到哪里')
        self.buttons()

    def choose(self):
        folder = filedialog.askdirectory(parent=self.window, title='选择要整理的文件夹', mustexist=True)
        if folder:
            self.folder.set(folder)

    def append_log(self, line):
        self.log.configure(state='normal')
        self.log.insert('end', str(line) + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def start(self, task, message):
        self.busy = True
        self.status.set(message)
        self.buttons()
        self.progress.start(12)

        def worker():
            try:
                self.events.put(('done', task()))
            except Exception as exc:
                self.events.put(('error', str(exc)))

        threading.Thread(target=worker, daemon=False).start()

    def prepare(self, mode):
        folder = self.folder.get().strip()
        self.preview = None
        self.table.delete(*self.table.get_children())
        gui_theme.show_empty(self, '正在生成方案…', '这里只读取文件信息，请稍候')
        self.start(lambda: gui_actions.prepare(folder, mode), '正在读取文件夹，请稍候…')

    def execute(self):
        preview = self.preview
        if not preview or self.busy:
            return
        self.preview = None  # one preview grants only one execution
        self.append_log(f'\n开始{ "整理" if preview.mode == "tidy" else "撤销"}：{preview.root}')
        self.start(lambda: gui_actions.apply(preview, lambda line: self.events.put(('log', line))),
                   '正在处理文件，请保留窗口；大文件核对可能需要一些时间…')

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log':
                    self.append_log(value)
                    continue
                self.busy = False
                self.progress.stop()
                if kind == 'error':
                    self.preview = None
                    self.status.set('操作未完成，请查看下方原因并重新预览')
                    self.summary.set('请重新预览')
                    self.table.delete(*self.table.get_children())
                    gui_theme.update_stats(self)
                    gui_theme.show_empty(self, '需要重新预览', '查看下方记录，处理问题后可以重试')
                    self.append_log('错误：' + value)
                    messagebox.showerror('操作未完成', value, parent=self.window)
                elif isinstance(value, gui_actions.Preview):
                    self.preview = value
                    self.summary.set(value.summary)
                    gui_theme.update_stats(self, value)
                    self.list_title.set('撤销预览' if value.mode == 'undo' else '整理预览')
                    self.empty.place_forget()
                    for index, row in enumerate(value.rows):
                        self.table.insert('', 'end', values=row, tags=(
                            'odd' if index % 2 else 'even', 'skip' if row[0] == '跳过' else 'move'))
                    if not value.rows:
                        gui_theme.show_empty(self, '没有可撤销的记录' if value.mode == 'undo' else '文件夹里没有待整理的文件',
                                             '可以选择其他文件夹再试一次')
                    self.status.set('预览完成，文件尚未移动。点击“开始整理”或“确认撤销”才会操作。')
                    self.append_log(value.summary)
                else:
                    self.table.delete(*self.table.get_children())
                    self.summary.set('操作结束 · 请重新预览查看当前文件')
                    gui_theme.update_stats(self)
                    gui_theme.show_empty(self, '本次操作已完成' if value else '部分文件需要处理',
                                         '详细结果见下方记录 · 再次预览可查看当前文件')
                    self.status.set('操作完成' if value else '部分文件未完成，请查看日志；其他文件已处理。')
                self.buttons()
        except queue.Empty:
            pass
        self.poll_id = self.window.after(80, self.poll)

    def on_destroy(self, event):
        if event.widget is self.window:
            self.window.after_cancel(self.poll_id)

    def close(self):
        if self.busy:
            messagebox.showinfo('正在处理', '请等本次操作结束后再关闭窗口。', parent=self.window)
        else:
            self.window.destroy()


def main():
    window = tk.Tk()
    TidyApp(window)
    window.mainloop()


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        import release_smoke
        release_smoke.run(sys.argv[2])
    elif sys.argv[1:] == ['--install-desktop']:
        import desktop_install
        sys.exit(desktop_install.run())
    else:
        main()
