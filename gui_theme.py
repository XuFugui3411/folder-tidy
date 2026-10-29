"""Warm desktop styling, drawn with standard Tk/ttk only."""
import tkinter as tk
from tkinter import ttk

BG = '#f6f3ef'
INK = '#30292b'
MUTED = '#82787b'
RED = '#73283f'
LINE = '#e9e2df'
WHITE = '#ffffff'
FONT = 'Microsoft YaHei UI'


def label(parent, text='', size=10, color=INK, bg=WHITE, bold=False, **kwargs):
    return tk.Label(parent, text=text, font=(FONT, size, 'bold' if bold else 'normal'),
                    fg=color, bg=bg, borderwidth=0, **kwargs)


def folder_icon(canvas, x, y, scale=1, outline=RED, fill='#f7edf0'):
    points = [0, 7, 0, 0, 21, 0, 29, 8, 62, 8, 62, 45, 0, 45]
    canvas.create_polygon(*[v * scale + (x if i % 2 == 0 else y) for i, v in enumerate(points)],
                          fill=fill, outline=outline, width=2, joinstyle='round')
    canvas.create_line(x, y + 14 * scale, x + 62 * scale, y + 14 * scale,
                       fill=outline, width=2)


def styles(window):
    style = ttk.Style(window)
    style.theme_use('clam')
    style.configure('.', font=(FONT, 10), background=WHITE, foreground=INK)
    style.configure('TButton', background=WHITE, foreground=INK, bordercolor=LINE,
                    lightcolor=WHITE, darkcolor=WHITE, borderwidth=1,
                    focuscolor=WHITE, padding=(16, 10))
    style.map('TButton', background=[('disabled', '#f5f2f1'), ('active', '#f6eff1')],
              foreground=[('disabled', '#aaa0a3')], bordercolor=[('active', '#c9a3af')])
    style.configure('Accent.TButton', background=RED, foreground=WHITE, bordercolor=RED,
                    lightcolor=RED, darkcolor=RED, focuscolor=RED, font=(FONT, 10, 'bold'))
    style.map('Accent.TButton', background=[('disabled', '#eee5e8'), ('active', '#8b3651')],
              foreground=[('disabled', '#b99ea7')], bordercolor=[('disabled', '#eee5e8'), ('active', '#8b3651')],
              lightcolor=[('disabled', '#eee5e8')], darkcolor=[('disabled', '#eee5e8')])
    style.configure('TEntry', padding=10, fieldbackground='#faf8f6', foreground=INK,
                    bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, insertcolor=RED)
    style.map('TEntry', bordercolor=[('focus', '#b77e90')], lightcolor=[('focus', '#b77e90')])
    style.configure('Treeview', rowheight=38, background=WHITE, fieldbackground=WHITE,
                    foreground=INK, borderwidth=0, lightcolor=WHITE, darkcolor=WHITE)
    style.configure('Treeview.Heading', background='#faf8f6', foreground=MUTED,
                    bordercolor='#faf8f6', lightcolor='#faf8f6', darkcolor='#faf8f6',
                    font=(FONT, 9), padding=(12, 12), relief='flat')
    style.map('Treeview', background=[('selected', '#f0dfe5')], foreground=[('selected', RED)])
    style.map('Treeview.Heading', background=[('active', '#f3ece9')])
    style.layout('Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])
    for orientation in ('Vertical', 'Horizontal'):
        style.configure(f'{orientation}.TScrollbar', background='#ded4d4', troughcolor='#faf8f6',
                        bordercolor=WHITE, arrowcolor=MUTED, lightcolor=WHITE, darkcolor=WHITE,
                        gripcount=0, arrowsize=11, borderwidth=0)
    style.configure('TProgressbar', background=RED, troughcolor='#f1e9e9',
                    bordercolor=BG, lightcolor=RED, darkcolor=RED, thickness=3)


def build(app, window):
    styles(window)
    window.title('Folder Tidy · 文件整理助手')
    width = min(1180, window.winfo_screenwidth() - 60)
    height = min(860, window.winfo_screenheight() - 100)
    window.geometry(f'{width}x{height}')
    window.minsize(980, 780)
    window.configure(background=BG)
    window.columnconfigure(1, weight=1)
    window.rowconfigure(0, weight=1)
    window.tidy_icon = tk.PhotoImage(width=32, height=32)
    window.tidy_icon.put(RED, to=(3, 1, 29, 31))
    window.tidy_icon.put(RED, to=(1, 3, 31, 29))
    window.tidy_icon.put('#f6e9dd', to=(6, 9, 15, 11))
    window.tidy_icon.put('#f6e9dd', to=(6, 11, 26, 13))
    window.tidy_icon.put('#f6e9dd', to=(6, 13, 8, 24))
    window.tidy_icon.put('#f6e9dd', to=(24, 13, 26, 24))
    window.tidy_icon.put('#f6e9dd', to=(6, 22, 26, 24))
    window.iconphoto(True, window.tidy_icon)

    side = tk.Frame(window, bg='#542032', width=196)
    side.grid(row=0, column=0, sticky='ns')
    side.grid_propagate(False)
    logo = tk.Canvas(side, bg='#542032', height=94, width=140, highlightthickness=0)
    logo.pack(anchor='w', padx=27, pady=(34, 0))
    folder_icon(logo, 3, 5, .68, outline='#e5c2a5', fill='#542032')
    logo.create_text(3, 65, text='FOLDER TIDY', anchor='w', fill='#fbf4ec', font=('Segoe UI', 14, 'bold'))
    label(side, '给文件一个归处', size=10, color='#d6b7c1', bg='#542032').pack(anchor='w', padx=27, pady=(0, 32))
    tk.Frame(side, height=1, bg='#774353').pack(fill='x', padx=27)
    label(side, 'WORKSPACE', size=8, color='#c49dab', bg='#542032').pack(anchor='w', padx=27, pady=(25, 17))
    nav = tk.Frame(side, bg='#75334a', padx=15, pady=12)
    nav.pack(fill='x', padx=14)
    label(nav, '▣   文件整理', size=11, bg='#75334a', color='#fff6f1', bold=True).pack(anchor='w')
    label(side, '操作顺序', size=9, color='#c49dab', bg='#542032').pack(anchor='w', padx=28, pady=(36, 15))
    for num, title, subtitle in [('01', '选择文件夹', '确定整理的范围'), ('02', '预览方案', '查看每个文件的去向'), ('03', '确认执行', '需要时可以撤销')]:
        row = tk.Frame(side, bg='#542032')
        row.pack(anchor='w', padx=28, pady=(0, 20))
        label(row, num, size=9, color='#dcbca3', bg='#542032').grid(row=0, column=0, sticky='nw', padx=(0, 10), pady=2)
        label(row, title, size=10, color='#f9e9ed', bg='#542032').grid(row=0, column=1, sticky='w')
        label(row, subtitle, size=8, color='#c49dab', bg='#542032').grid(row=1, column=1, sticky='w', pady=(4, 0))
    bottom = tk.Frame(side, bg='#542032')
    bottom.pack(side='bottom', fill='x', padx=27, pady=26)
    label(bottom, '●  文件留在本机', size=9, color='#ead4dc', bg='#542032').pack(anchor='w')
    label(bottom, '不上传文件 · 无需联网', size=8, color='#c49dab', bg='#542032').pack(anchor='w', pady=(7, 0))

    body = tk.Frame(window, bg=BG, padx=28, pady=24)
    body.grid(row=0, column=1, sticky='nsew')
    body.columnconfigure(0, weight=1)
    body.rowconfigure(3, weight=1)
    header = tk.Frame(body, bg=BG)
    header.grid(row=0, column=0, sticky='ew', pady=(0, 19))
    label(header, '文件整理', size=23, bg=BG, bold=True).pack(anchor='w')
    label(header, '先看清每一份文件的去向，再开始整理。', size=10, color=MUTED, bg=BG).pack(anchor='w', pady=(6, 0))
    label(header, '本地工作台', size=9, color=RED, bg='#eee3e5', padx=12, pady=7).place(relx=1, x=0, y=8, anchor='ne')

    path_card = tk.Frame(body, bg=WHITE, highlightbackground=LINE, highlightthickness=1, padx=18, pady=14)
    path_card.grid(row=1, column=0, sticky='ew', pady=(0, 14))
    label(path_card, '整理位置', size=10, bold=True).pack(anchor='w', pady=(0, 9))
    path_row = tk.Frame(path_card, bg=WHITE)
    path_row.pack(fill='x')
    app.folder = tk.StringVar()
    app.path_input = ttk.Entry(path_row, textvariable=app.folder, font=(FONT, 10))
    app.path_input.pack(side='left', fill='x', expand=True)
    app.choose_button = ttk.Button(path_row, text='选择文件夹…', style='Accent.TButton', command=app.choose)
    app.choose_button.pack(side='left', padx=(10, 0))
    label(path_card, '文件将归入这个文件夹内的分类子目录。', size=9, color=MUTED).pack(anchor='w', pady=(8, 0))

    stats = tk.Frame(body, bg=BG)
    stats.grid(row=2, column=0, sticky='ew', pady=(0, 14))
    app.stat_values = [tk.StringVar(value='—') for _ in range(3)]
    app.stat_titles = [tk.StringVar(value=t) for t in ('扫描项目', '计划移动', '跳过项目')]
    for i, (title, value) in enumerate(zip(app.stat_titles, app.stat_values)):
        stats.columnconfigure(i, weight=1, uniform='stat')
        card = tk.Frame(stats, bg='#f0e3e7' if i == 1 else WHITE, padx=17, pady=10,
                        highlightbackground='#e6d3da' if i == 1 else LINE, highlightthickness=1)
        card.grid(row=0, column=i, sticky='ew', padx=(0, 10) if i < 2 else 0)
        card_bg = card.cget('bg')
        label(card, textvariable=title, size=9, bg=card_bg, color=MUTED).pack(anchor='w')
        label(card, textvariable=value, size=23, bg=card_bg, color=RED if i == 1 else INK,
              bold=True).pack(anchor='w', pady=(1, 0))

    preview_card = tk.Frame(body, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
    preview_card.grid(row=3, column=0, sticky='nsew')
    preview_card.columnconfigure(0, weight=1)
    preview_card.rowconfigure(1, weight=1)
    heading = tk.Frame(preview_card, bg=WHITE, padx=18, pady=12)
    heading.grid(row=0, column=0, sticky='ew')
    app.list_title = tk.StringVar(value='整理预览')
    label(heading, textvariable=app.list_title, size=12, bold=True).pack(anchor='w')
    app.summary = tk.StringVar(value='选择文件夹后，生成你的整理方案。')
    label(heading, textvariable=app.summary, size=9, color=MUTED).pack(anchor='w', pady=(4, 0))
    table_frame = tk.Frame(preview_card, bg=WHITE)
    table_frame.grid(row=1, column=0, sticky='nsew')
    table_frame.rowconfigure(0, weight=1)
    table_frame.columnconfigure(0, weight=1)
    app.table = ttk.Treeview(table_frame, columns=('state', 'source', 'target'), show='headings', height=3)
    for key, title, width in [('state', '操作', 92), ('source', '当前文件', 220), ('target', '目标位置 / 说明', 360)]:
        app.table.heading(key, text=title, anchor='w')
        app.table.column(key, width=width, minwidth=70, stretch=key != 'state', anchor='w')
    sy = ttk.Scrollbar(table_frame, orient='vertical', command=app.table.yview)
    sx = ttk.Scrollbar(table_frame, orient='horizontal', command=app.table.xview)
    app.table.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    app.table.grid(row=0, column=0, sticky='nsew')
    sy.grid(row=0, column=1, sticky='ns')
    sx.grid(row=1, column=0, sticky='ew')
    app.table.tag_configure('even', background=WHITE)
    app.table.tag_configure('odd', background='#fcfaf8')
    app.table.tag_configure('skip', foreground='#9a8d80')
    app.table.tag_configure('move', foreground=RED)
    app.empty = tk.Frame(table_frame, bg=WHITE)
    icon = tk.Canvas(app.empty, width=90, height=64, bg=WHITE, highlightthickness=0)
    icon.pack()
    folder_icon(icon, 12, 7, 1, outline='#b98a98', fill='#f8f0f2')
    icon.create_line(35, 35, 48, 35, fill='#b98a98', width=2)
    app.empty_title = tk.StringVar(value='从一个文件夹开始')
    app.empty_hint = tk.StringVar(value='点击上方「选择文件夹」，然后预览整理方案')
    label(app.empty, textvariable=app.empty_title, size=11, bold=True).pack(pady=(6, 6))
    label(app.empty, textvariable=app.empty_hint, size=9, color=MUTED).pack()
    app.empty.place(relx=.5, rely=.66 if app.empty.master.winfo_height() < 200 else .56, anchor='center')

    def fit_empty(event):
        # Preserve space for the table heading at smaller window heights.
        if event.height < 200:
            icon.pack_forget()
        elif not icon.winfo_manager():
            icon.pack(before=app.empty.winfo_children()[1])
        if app.empty.winfo_manager():
            app.empty.place_configure(rely=.66 if event.height < 200 else .56)

    table_frame.bind('<Configure>', fit_empty)

    action_bar = tk.Frame(preview_card, bg=WHITE, padx=14, pady=12)
    action_bar.grid(row=2, column=0, sticky='ew')
    app.preview_button = ttk.Button(action_bar, text='预览整理', command=lambda: app.prepare('tidy'))
    app.preview_button.pack(side='left')
    app.undo_preview_button = ttk.Button(action_bar, text='预览撤销', command=lambda: app.prepare('undo'))
    app.undo_preview_button.pack(side='left', padx=(8, 0))
    app.apply_button = ttk.Button(action_bar, text='开始整理  →', style='Accent.TButton', command=app.execute)
    app.apply_button.pack(side='right')
    app.undo_button = ttk.Button(action_bar, text='确认撤销', style='Accent.TButton', command=app.execute)
    # The primary action switches with the preview mode.
    app.controls = [app.path_input, app.choose_button, app.preview_button, app.undo_preview_button]

    footer = tk.Frame(body, bg=BG)
    footer.grid(row=4, column=0, sticky='ew', pady=(10, 0))
    app.status = tk.StringVar(value='准备就绪 · 尚未移动任何文件')
    app.status_label = label(footer, textvariable=app.status, size=9, color=MUTED, bg=BG, anchor='w', justify='left')
    app.status_label.pack(fill='x')
    footer.bind('<Configure>', lambda e: app.status_label.configure(wraplength=max(200, e.width - 10)))
    app.progress = ttk.Progressbar(footer, mode='indeterminate')
    app.progress.pack(fill='x', pady=(7, 8))
    log_frame = tk.Frame(footer, bg='#eee9e5', padx=10, pady=7)
    log_frame.pack(fill='x')
    label(log_frame, '操作记录', size=8, color=MUTED, bg='#eee9e5').pack(anchor='w')
    app.log = tk.Text(log_frame, height=2, font=(FONT, 9), wrap='word', relief='flat', borderwidth=0,
                      state='disabled', bg='#eee9e5', fg='#6c5e63', highlightthickness=0)
    log_scroll = ttk.Scrollbar(log_frame, command=app.log.yview)
    app.log.configure(yscrollcommand=log_scroll.set)
    app.log.pack(side='left', fill='both', expand=True, pady=(3, 0))
    log_scroll.pack(side='right', fill='y')
    app.folder.trace_add('write', app.invalidate)


def show_empty(app, title='从一个文件夹开始', hint='点击上方「选择文件夹」，然后预览整理方案'):
    app.empty_title.set(title)
    app.empty_hint.set(hint)
    app.empty.place(relx=.5, rely=.66 if app.empty.master.winfo_height() < 200 else .56, anchor='center')


def update_stats(app, preview=None):
    if preview is None:
        titles, values = ('扫描项目', '计划移动', '跳过项目'), ('—', '—', '—')
    elif preview.mode == 'tidy':
        p = preview.plan
        titles, values = ('扫描项目', '计划移动', '跳过项目'), (p['scanned'], len(p['moves']), len(p['skipped']))
    else:
        titles, values = ('撤销记录', '计划还原', '核对方式'), (1 if preview.rows else 0, len(preview.rows), '逐项核对')
    for title_var, value_var, title, value in zip(app.stat_titles, app.stat_values, titles, values):
        title_var.set(title)
        value_var.set(str(value))
