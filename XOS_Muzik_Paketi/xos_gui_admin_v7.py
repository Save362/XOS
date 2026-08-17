#!/usr/bin/env python3
"""
X OS - Arayüzlü Sanal İşletim Sistemi (v2)
- Uygulamalar ayrı OS pencereleri değil, masaüstü içinde sürüklenebilir
  kendi panelleri (internal window) olarak açılır.
- Eski tip (retro BIOS) açılış ekranı eklendi.
"""

import tkinter as tk
import urllib.request
import json
from tkinter import font as tkfont
from tkinter import messagebox
import datetime
import random
import sys
import os
from pathlib import Path
try:
    import winsound
except ImportError:
    winsound = None

APP_NAME = "X OS"
VERSION = "1.0"

# ----------------------------------------------------------------------
# Renk / stil paleti
# ----------------------------------------------------------------------
BG_DESKTOP = "#0f2740"
TASKBAR_BG = "#111827"
TASKBAR_FG = "#e5e7eb"
ACCENT = "#3b82f6"
ICON_FG = "#ffffff"
WINDOW_TITLE_BG = "#1f2937"
WINDOW_BG = "#f3f4f6"
BOOT_BG = "#000000"
BOOT_FG = "#33ff33"

WIN_WIDTH, WIN_HEIGHT = 1000, 650


# ----------------------------------------------------------------------
# Basit sanal dosya sistemi (Dosya Yöneticisi için)
# ----------------------------------------------------------------------

# ============================================================
# X OS UPDATE CONFIGURATION
# ============================================================
XOS_VERSION = "9.0"
XOS_GITHUB_OWNER = "YOUR_GITHUB_USERNAME"
XOS_GITHUB_REPO = "YOUR_XOS_REPOSITORY"
XOS_RELEASE_ASSET = "xos_gui_admin.py"

class VFile:
    def __init__(self, name, content=""):
        self.name = name
        self.content = content


class VDir:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.dirs = {}
        self.files = {}


class VFS:
    def __init__(self):
        self.root = VDir("")
        for d in ["Belgeler", "Indirilenler", "Masaustu"]:
            self.root.dirs[d] = VDir(d, self.root)
        self.root.files["oku_beni.txt"] = VFile(
            "oku_beni.txt", f"{APP_NAME}'a hoş geldiniz!\nBu dosyayı Dosya Yöneticisi ile açtınız."
        )
        self.root.files["admin"] = VFile(
            "admin", "X OS Yönetici Test Paneli\nŞifre korumalı."
        )
        self.root.files["admin"] = VFile("admin", "X OS yönetici test paneli")


# ----------------------------------------------------------------------
# İç pencere (masaüstüne bağlı, sürüklenebilir panel)
# ----------------------------------------------------------------------
class InternalWindow(tk.Frame):
    _z_counter = 10

    def __init__(self, desktop, title, x=80, y=40, width=380, height=340):
        super().__init__(desktop, bg=WINDOW_BG, highlightthickness=1,
                          highlightbackground="#374151", highlightcolor="#374151")
        self.desktop = desktop
        self.place(x=x, y=y, width=width, height=height)

        self.title_bar = tk.Frame(self, bg=WINDOW_TITLE_BG, height=28)
        self.title_bar.pack(fill="x", side="top")
        self.title_bar.pack_propagate(False)

        tk.Label(self.title_bar, text=title, bg=WINDOW_TITLE_BG, fg="white",
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=8)

        close_btn = tk.Button(self.title_bar, text="✕", command=self.animate_close,
                               bg=WINDOW_TITLE_BG, fg="white", bd=0,
                               activebackground="#ef4444", activeforeground="white",
                               font=("Segoe UI", 10, "bold"), cursor="hand2")
        close_btn.pack(side="right", padx=4)

        # İçerik alanı - uygulamalar buraya widget ekler
        self.content = tk.Frame(self, bg=WINDOW_BG)
        self.content.pack(fill="both", expand=True)

        self._drag = {"x": 0, "y": 0}
        self.title_bar.bind("<ButtonPress-1>", self._start_drag)
        self.title_bar.bind("<B1-Motion>", self._do_drag)
        self.title_bar.bind("<ButtonRelease-1>", lambda e: self.raise_up())
        self.bind("<ButtonPress-1>", lambda e: self.raise_up())

        self.raise_up()

    def animate_close(self, callback=None):
        """Paneli küçülterek/kaybolarak kapatır."""
        try:
            x, y = self.winfo_x(), self.winfo_y()
            w, h = self.winfo_width(), self.winfo_height()
            step = {"n": 0}
            steps = 8

            def shrink():
                if not self.winfo_exists():
                    if callback:
                        callback()
                    return

                i = step["n"]
                if i >= steps:
                    self.destroy()
                    if callback:
                        callback()
                    return

                nw = max(40, int(w * (1 - (i + 1) / steps)))
                nh = max(30, int(h * (1 - (i + 1) / steps)))
                nx = x + (w - nw) // 2
                ny = y + (h - nh) // 2
                self.place(x=nx, y=ny, width=nw, height=nh)
                step["n"] += 1
                self.after(25, shrink)

            shrink()

        except tk.TclError:
            if callback:
                callback()

    def raise_up(self):
        InternalWindow._z_counter += 1
        self.lift()

    def _start_drag(self, event):
        self._drag["x"] = event.x
        self._drag["y"] = event.y
        self.raise_up()

    def _do_drag(self, event):
        dx = event.x - self._drag["x"]
        dy = event.y - self._drag["y"]
        new_x = self.winfo_x() + dx
        new_y = self.winfo_y() + dy
        # masaüstü sınırları içinde tut
        new_x = max(0, min(new_x, self.desktop.winfo_width() - 40))
        new_y = max(0, min(new_y, self.desktop.winfo_height() - 30))
        self.place(x=new_x, y=new_y)


# ----------------------------------------------------------------------
# Ana Uygulama
# ----------------------------------------------------------------------
class XOS(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry(f"{WIN_WIDTH}x{WIN_HEIGHT}")
        self.configure(bg=BOOT_BG)
        self.resizable(True, True)

        self.vfs = VFS()
        self.todos = []
        self._open_offset = 0
        self.safe_mode = False
        self.safe_mode_after_boot = False
        self.music_playing = False
        self.music_file = None
        self.music_player_process = None
        self._safe_mode = False

        self.icon_font = tkfont.Font(family="Segoe UI", size=10)
        self.clock_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")

        self._show_boot_screen()

    # ====================================================================
    # ESKİ TİP (RETRO) AÇILIŞ EKRANI
    # ====================================================================
    def _show_boot_screen(self):
        self.boot_frame = tk.Frame(self, bg=BOOT_BG)
        self.boot_frame.place(x=0, y=0, relwidth=1, relheight=1)

        self.boot_text = tk.Text(
            self.boot_frame, bg=BOOT_BG, fg=BOOT_FG, bd=0, highlightthickness=0,
            font=("Courier New", 13), insertbackground=BOOT_FG, cursor="none"
        )
        self.boot_text.pack(expand=True, fill="both", padx=50, pady=40)
        self.boot_text.configure(state="disabled")

        ascii_logo = [
            r"__  __     ____   _____ ",
            r"\ \/ /    / __ \ / ____|",
            r" \  /____| |  | | (___  ",
            r" /  \____| |  | |\___ \ ",
            r"/_/\_\    | |__| |____) |",
            r"           \____/|_____/ ",
        ]

        boot_lines = [
            f"{APP_NAME} BIOS v{VERSION}",
            "Copyright (C) X Systems Inc.",
            "",
            "CPU: Virtual x86-64 @ 3.20GHz",
            "640K Base Memory, 65536K Extended Memory",
            "",
            "Bellek denetleniyor... OK",
            "Disk denetleniyor......... OK",
            "Klavye denetleniyor....... OK",
            "Sanal dosya sistemi bağlanıyor... OK",
            "",
            "Çekirdek yükleniyor...",
        ]

        self._boot_queue = []
        self._boot_queue.extend(("logo", l) for l in ascii_logo)
        self._boot_queue.append(("blank", ""))
        self._boot_queue.extend(("line", l) for l in boot_lines)
        self._boot_queue.append(("bar", ""))
        self._boot_queue.append(("final", f"{APP_NAME} başlatılıyor, lütfen bekleyin..."))

        self._boot_step(0)

    def _boot_append(self, text, newline=True):
        self.boot_text.configure(state="normal")
        self.boot_text.insert("end", text + ("\n" if newline else ""))
        self.boot_text.see("end")
        self.boot_text.configure(state="disabled")

    def _boot_step(self, idx):
        if idx >= len(self._boot_queue):
            self.after(500, self._finish_boot)
            return

        kind, content = self._boot_queue[idx]

        if kind in ("logo", "line", "blank"):
            self._boot_append(content)
            delay = 45 if kind == "logo" else (120 if content else 60)
            self.after(delay, lambda: self._boot_step(idx + 1))

        elif kind == "bar":
            self._boot_append("Yükleniyor: [", newline=False)
            self._boot_progress(0, idx)

        elif kind == "final":
            self._boot_append(content)
            self.after(700, lambda: self._boot_step(idx + 1))

    def _boot_progress(self, pct, idx):
        if pct == 0:
            self._bar_chars = 0
        total_blocks = 24
        target_blocks = int((pct / 100) * total_blocks)
        new_blocks = target_blocks - self._bar_chars
        if new_blocks > 0:
            self.boot_text.configure(state="normal")
            self.boot_text.insert("end", "#" * new_blocks)
            self.boot_text.see("end")
            self.boot_text.configure(state="disabled")
            self._bar_chars = target_blocks

        if pct >= 100:
            self._boot_append("] 100%")
            self.after(200, lambda: self._boot_step(idx + 1))
        else:
            self.after(30, lambda: self._boot_progress(pct + random.randint(3, 9), idx))

    def _finish_boot(self):
        self.boot_frame.destroy()
        self.configure(bg=BG_DESKTOP)

        # Every normal boot starts in normal mode.
        if not getattr(self, "safe_mode_after_boot", False):
            self.safe_mode = False

        self._build_desktop()
        self._build_taskbar()
        self._update_clock()

        if getattr(self, "safe_mode_after_boot", False):
            self.safe_mode_after_boot = False
            self.show_safe_mode_label()
        if self._safe_mode:
            self._show_safe_mode_label()

    def open_start_center(self):
        win = self._new_panel(
            "X OS Başlat",
            470,
            480
        )

        self.update_idletasks()
        x = max(20, (self.desktop.winfo_width() - 470) // 2)
        y = max(20, (self.desktop.winfo_height() - 480) // 2)

        win.place(
            x=x, y=y,
            width=470,
            height=480
        )

        c = win.content

        tk.Label(
            c,
            text="X OS",
            bg=WINDOW_BG,
            font=("Segoe UI", 22, "bold")
        ).pack(pady=(18, 2))

        tk.Label(
            c,
            text="Başlat",
            bg=WINDOW_BG,
            fg="#6b7280"
        ).pack(pady=(0, 12))

        apps = [
            ("🧮 Hesap Makinesi", self.open_calculator),
            ("📝 Not Defteri", self.open_notepad),
            ("📁 Dosya Yöneticisi", self.open_files),
            ("🕒 Saat & Takvim", self.open_clock_app),
            ("🎵 Müzik Çalar", self.open_music_player),
            ("🐍 Yılan + Labirent", self.open_snake_maze),
            ("🔄 XUpdateTool", self.open_xupdate_tool),
            ("🎮 Sayı Tahmin", self.open_game),
            ("ℹ️ Sistem Bilgisi", self.open_sysinfo),
            ("🔐 admin", self.open_admin),
        ]

        grid = tk.Frame(c, bg=WINDOW_BG)
        grid.pack(fill="both", expand=True, padx=22)

        for i, (label, command) in enumerate(apps):
            def launch(cmd=command):
                win.animate_close(
                    lambda: self.after(30, cmd)
                )

            tk.Button(
                grid,
                text=label,
                command=launch,
                bg="white",
                fg="#111827",
                relief="flat",
                anchor="w",
                padx=12,
                pady=10
            ).grid(
                row=i // 2,
                column=i % 2,
                sticky="nsew",
                padx=4,
                pady=4
            )

        for col in range(2):
            grid.columnconfigure(col, weight=1)

        power = tk.Frame(c, bg=WINDOW_BG)
        power.pack(fill="x", padx=22, pady=12)

        tk.Button(
            power,
            text="↻ Yeniden Başlat",
            command=lambda: (
                win.animate_close(
                    lambda: self.after(80, self.restart_xos)
                )
            ),
            bg="#374151",
            fg="white",
            relief="flat",
            padx=10,
            pady=8
        ).pack(side="left", expand=True, fill="x", padx=3)

        tk.Button(
            power,
            text="⏻ Kapat",
            command=lambda: (
                win.animate_close(
                    lambda: self.after(80, self.animate_shutdown)
                )
            ),
            bg="#7f1d1d",
            fg="white",
            relief="flat",
            padx=10,
            pady=8
        ).pack(side="left", expand=True, fill="x", padx=3)

    # ====================================================================
    # YENİDEN BAŞLAT / KAPATMA ANİMASYONLARI
    # ====================================================================

    def _center_overlay(self, title, message, progress=False):
        overlay = tk.Frame(self, bg="#0b1220")
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        overlay.lift()

        card = tk.Frame(
            overlay,
            bg="#111827",
            highlightthickness=1,
            highlightbackground="#374151"
        )
        card.place(relx=0.5, rely=0.5, anchor="center", width=430, height=220)

        tk.Label(
            card, text=title,
            bg="#111827", fg="white",
            font=("Segoe UI", 20, "bold")
        ).pack(pady=(38, 10))

        msg = tk.Label(
            card, text=message,
            bg="#111827", fg="#cbd5e1",
            font=("Segoe UI", 10)
        )
        msg.pack(pady=5)

        bar = None
        if progress:
            bar = tk.Frame(card, bg="#374151", height=8)
            bar.pack(fill="x", padx=55, pady=20)
            fill = tk.Frame(bar, bg="#3b82f6", height=8)
            fill.place(x=0, y=0, relheight=1, relwidth=0)

        return overlay, card, msg, fill if progress else None

    def restart_xos(self):
        """X OS'u gerçek bilgisayarı yeniden başlatmadan animasyonla yeniden başlatır."""
        self._animate_restart()

    def _animate_restart(self):
        for widget in list(self.winfo_children()):
            if widget not in (getattr(self, "boot_frame", None),):
                try:
                    if isinstance(widget, InternalWindow):
                        widget.animate_close()
                except Exception:
                    pass

        overlay, card, msg, fill = self._center_overlay(
            "↻ Yeniden Başlatılıyor",
            "X OS yeniden başlatılıyor...",
            progress=True
        )

        def step(p=0):
            if not overlay.winfo_exists():
                return
            if p >= 100:
                msg.config(text="Açılış ekranı hazırlanıyor...")
                self.after(400, lambda: finish())
                return
            fill.place_configure(relwidth=p / 100)
            self.after(18, lambda: step(min(100, p + 4)))

        def finish():
            overlay.destroy()
            self.safe_mode = False
            self.safe_mode_after_boot = False
            if hasattr(self, "desktop"):
                try:
                    self.desktop.destroy()
                except tk.TclError:
                    pass
            if hasattr(self, "taskbar"):
                try:
                    self.taskbar.destroy()
                except tk.TclError:
                    pass

            self.safe_mode = False
            self.safe_mode_after_boot = False
            self.configure(bg=BOOT_BG)
            self._show_boot_screen()

        step()

    def animate_shutdown(self):
        """X OS'u animasyonla kapatır ve ortada açma düğmesi gösterir."""
        self._stop_music()
        overlay, card, msg, fill = self._center_overlay(
            "X OS Kapatılıyor",
            "Oturum kapatılıyor...",
            progress=True
        )

        def step(p=0):
            if not overlay.winfo_exists():
                return
            if p >= 100:
                msg.config(text="Ekran kapatılıyor...")
                self.after(500, lambda: finish())
                return
            fill.place_configure(relwidth=p / 100)
            self.after(22, lambda: step(min(100, p + 5)))

        def finish():
            overlay.destroy()
            if hasattr(self, "desktop"):
                try:
                    self.desktop.place_forget()
                except tk.TclError:
                    pass
            if hasattr(self, "taskbar"):
                try:
                    self.taskbar.place_forget()
                except tk.TclError:
                    pass
            self._show_power_button_center()

        step()

    def _show_power_button_center(self):
        self.power_overlay = tk.Frame(self, bg="black")
        self.power_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.power_overlay.lift()

        card = tk.Frame(
            self.power_overlay,
            bg="#111827",
            highlightthickness=1,
            highlightbackground="#374151"
        )
        card.place(relx=0.5, rely=0.5, anchor="center", width=380, height=210)

        tk.Label(
            card,
            text="X OS kapalı",
            bg="#111827", fg="#e5e7eb",
            font=("Segoe UI", 18, "bold")
        ).pack(pady=(35, 8))

        tk.Button(
            card,
            text="⏻  X OS'u Aç",
            command=self.power_on_xos,
            bg="#2563eb", fg="white",
            activebackground="#3b82f6",
            relief="flat",
            font=("Segoe UI", 13, "bold"),
            padx=30, pady=12,
            cursor="hand2"
        ).pack(pady=20)

    def power_on_xos(self):
        try:
            self.power_overlay.destroy()
        except tk.TclError:
            pass

        # "Aç" normal boot yapar; güvenli moddan çıkılır.
        self.safe_mode = False
        self.safe_mode_after_boot = False
        self.configure(bg=BOOT_BG)
        self._show_boot_screen()

    # ====================================================================
    # DOSYA YÖNETİCİSİ EK İŞLEMLERİ
    # ====================================================================

    # ====================================================================
    # MASAÜSTÜ
    # ====================================================================
    def _build_desktop(self):
        self.desktop = tk.Frame(self, bg=BG_DESKTOP)
        self.desktop.place(x=0, y=0, relwidth=1, height=WIN_HEIGHT - 50)

        apps = [
            ("🧮", "Hesap\nMakinesi", self.open_calculator),
            ("📝", "Not\nDefteri", self.open_notepad),
            ("✅", "Yapılacaklar", self.open_todo),
            ("📁", "Dosya\nYöneticisi", self.open_files),
            ("🕒", "Saat &\nTakvim", self.open_clock_app),
            ("🎮", "Sayı\nTahmin", self.open_game),
            ("ℹ️", "Sistem\nBilgisi", self.open_sysinfo),
            ("🎵", "Müzik\nÇalar", self.open_music_player),
            ("🔐", "admin", self.open_admin),
        ]

        for i, (emoji, label, cmd) in enumerate(apps):
            frame = tk.Frame(self.desktop, bg=BG_DESKTOP)
            frame.place(x=20, y=20 + i * 90, width=90, height=85)

            btn = tk.Label(frame, text=emoji, font=("Segoe UI Emoji", 28),
                            bg=BG_DESKTOP, fg=ICON_FG, cursor="hand2")
            btn.pack()
            btn.bind("<Double-Button-1>", lambda e, c=cmd: c())

            lbl = tk.Label(frame, text=label, font=self.icon_font,
                            bg=BG_DESKTOP, fg=ICON_FG, justify="center")
            lbl.pack()
            lbl.bind("<Double-Button-1>", lambda e, c=cmd: c())

        hint = tk.Label(
            self.desktop, text="Uygulamaları açmak için simgelere çift tıklayın — pencereleri başlığından sürükleyebilirsin",
            bg=BG_DESKTOP, fg="#93c5fd", font=("Segoe UI", 9, "italic")
        )
        hint.place(relx=0.5, y=15, anchor="n")

    # ====================================================================
    # GÖREV ÇUBUĞU
    # ====================================================================
    def _build_taskbar(self):
        self.taskbar = tk.Frame(
            self,
            bg=TASKBAR_BG,
            height=50
        )
        self.taskbar.place(
            x=0, rely=1.0,
            relwidth=1, height=50,
            anchor="sw"
        )

        start_btn = tk.Button(
            self.taskbar,
            text=f"  {APP_NAME}  ",
            command=self.open_start_center,
            bg=ACCENT,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            cursor="hand2"
        )
        start_btn.pack(side="left", padx=(10, 4), pady=8)

        restart_btn = tk.Button(
            self.taskbar,
            text="↻ Yeniden Başlat",
            command=self.restart_xos,
            bg="#374151",
            fg="white",
            activebackground="#4b5563",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        restart_btn.pack(side="left", padx=4, pady=8)

        shutdown_btn = tk.Button(
            self.taskbar,
            text="⏻ Kapat",
            command=self.animate_shutdown,
            bg="#7f1d1d",
            fg="white",
            activebackground="#991b1b",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        shutdown_btn.pack(side="left", padx=4, pady=8)

        self.clock_label = tk.Label(
            self.taskbar,
            font=self.clock_font,
            bg=TASKBAR_BG,
            fg=TASKBAR_FG
        )
        self.clock_label.pack(side="right", padx=15)

    def _update_clock(self):
        # Yeniden başlatma / güvenli mod sırasında eski görev çubuğu
        # silinebileceği için etiketin hâlâ mevcut olduğunu kontrol et.
        try:
            if not hasattr(self, "clock_label"):
                return

            if not self.clock_label.winfo_exists():
                return

            now = datetime.datetime.now().strftime("%H:%M:%S   %d.%m.%Y")
            self.clock_label.config(text=now)

            self.after(1000, self._update_clock)

        except tk.TclError:
            # Eski görev çubuğu silindiyse zamanlayıcı sessizce sonlanır.
            return

    # ====================================================================
    # Yeni panel açma yardımcı fonksiyonu (kademeli konumlandırma)
    # ====================================================================
    def _new_panel(self, title, width=380, height=340):
        self._open_offset = (self._open_offset + 1) % 8
        x = 130 + self._open_offset * 25
        y = 30 + self._open_offset * 25
        return InternalWindow(self.desktop, title, x=x, y=y, width=width, height=height)

    # ====================================================================
    # UYGULAMALAR (artık InternalWindow paneli olarak açılıyor)
    # ====================================================================
    def open_calculator(self):
        win = self._new_panel("Hesap Makinesi", 260, 340)
        c = win.content

        entry_var = tk.StringVar()
        entry = tk.Entry(c, textvariable=entry_var, font=("Segoe UI", 16),
                          justify="right", bd=0, bg="white")
        entry.pack(fill="x", padx=8, pady=8, ipady=8)

        buttons = ["7", "8", "9", "/", "4", "5", "6", "*",
                   "1", "2", "3", "-", "0", ".", "=", "+", "C"]

        grid = tk.Frame(c, bg=WINDOW_BG)
        grid.pack(expand=True, fill="both", padx=8, pady=8)

        def press(ch):
            if ch == "C":
                entry_var.set("")
            elif ch == "=":
                try:
                    expr = entry_var.get()
                    allowed = "0123456789+-*/(). "
                    if all(ch2 in allowed for ch2 in expr):
                        entry_var.set(str(eval(expr)))
                    else:
                        entry_var.set("Hata")
                except Exception:
                    entry_var.set("Hata")
            else:
                entry_var.set(entry_var.get() + ch)

        r, col = 0, 0
        for b in buttons:
            btn = tk.Button(grid, text=b, font=("Segoe UI", 12), bg="#e5e7eb",
                             relief="flat", command=lambda ch=b: press(ch))
            btn.grid(row=r, column=col, sticky="nsew", padx=2, pady=2)
            col += 1
            if col > 3:
                col = 0
                r += 1
        for i in range(4):
            grid.columnconfigure(i, weight=1)
        for i in range(r + 1):
            grid.rowconfigure(i, weight=1)

    def open_notepad(self):
        win = self._new_panel("Not Defteri", 420, 380)
        c = win.content

        text = tk.Text(c, font=("Segoe UI", 11), wrap="word")
        text.pack(expand=True, fill="both", padx=6, pady=(6, 0))

        bar = tk.Frame(c, bg=WINDOW_BG)
        bar.pack(fill="x", padx=6, pady=6)

        name_var = tk.StringVar(value="not1.txt")
        tk.Entry(bar, textvariable=name_var, width=16).pack(side="left")

        def save():
            name = name_var.get().strip() or "not1.txt"
            content = text.get("1.0", "end-1c")
            self.vfs.root.files[name] = VFile(name, content)
            messagebox.showinfo(APP_NAME, f"'{name}' kaydedildi.", parent=win)

        tk.Button(bar, text="Kaydet", command=save, bg=ACCENT, fg="white",
                  relief="flat", padx=10).pack(side="left", padx=6)

    def open_todo(self):
        win = self._new_panel("Yapılacaklar Listesi", 340, 400)
        c = win.content

        listbox = tk.Listbox(c, font=("Segoe UI", 10), selectmode="single")
        listbox.pack(expand=True, fill="both", padx=6, pady=6)

        def refresh():
            listbox.delete(0, "end")
            for t in self.todos:
                mark = "[x]" if t["done"] else "[ ]"
                listbox.insert("end", f"{mark} {t['text']}")

        entry_var = tk.StringVar()
        bar = tk.Frame(c, bg=WINDOW_BG)
        bar.pack(fill="x", padx=6, pady=(0, 6))
        tk.Entry(bar, textvariable=entry_var).pack(side="left", expand=True, fill="x")

        def add_item():
            t = entry_var.get().strip()
            if t:
                self.todos.append({"text": t, "done": False})
                entry_var.set("")
                refresh()

        def toggle_done():
            sel = listbox.curselection()
            if sel:
                self.todos[sel[0]]["done"] = not self.todos[sel[0]]["done"]
                refresh()

        def delete_item():
            sel = listbox.curselection()
            if sel:
                self.todos.pop(sel[0])
                refresh()

        tk.Button(bar, text="Ekle", command=add_item, bg=ACCENT, fg="white",
                  relief="flat").pack(side="left", padx=4)
        bar2 = tk.Frame(c, bg=WINDOW_BG)
        bar2.pack(fill="x", padx=6, pady=(0, 6))
        tk.Button(bar2, text="Tamamla/Geri Al", command=toggle_done).pack(side="left", padx=4)
        tk.Button(bar2, text="Sil", command=delete_item).pack(side="left", padx=4)

        refresh()

    def open_files(self):
        win = self._new_panel("Dosya Yöneticisi", 620, 470)
        c = win.content

        state = {
            "cwd": self.vfs.root,
            "drag_name": None,
            "drag_kind": None,
        }

        top = tk.Frame(c, bg=WINDOW_BG)
        top.pack(fill="x", padx=7, pady=7)

        path_label = tk.Label(
            top,
            text="/",
            bg=WINDOW_BG,
            font=("Segoe UI", 10, "bold")
        )
        path_label.pack(side="left")

        body = tk.Frame(c, bg=WINDOW_BG)
        body.pack(expand=True, fill="both", padx=7)

        listbox = tk.Listbox(
            body,
            font=("Segoe UI", 10),
            selectmode="single",
            activestyle="none"
        )
        listbox.pack(side="left", expand=True, fill="both")

        preview = tk.Text(
            body,
            width=30,
            font=("Segoe UI", 9),
            state="disabled"
        )
        preview.pack(side="right", fill="both", padx=(7, 0))

        def path_text(node):
            parts = []
            while node.parent is not None:
                parts.append(node.name)
                node = node.parent
            return "/" + "/".join(reversed(parts))

        def refresh():
            listbox.delete(0, "end")

            for name in sorted(state["cwd"].dirs):
                listbox.insert("end", "📁 " + name)

            for name in sorted(state["cwd"].files):
                listbox.insert("end", "📄 " + name)

            path_label.config(text=path_text(state["cwd"]))

            preview.config(state="normal")
            preview.delete("1.0", "end")
            preview.config(state="disabled")

        def selected():
            indexes = listbox.curselection()
            if not indexes:
                return None, None

            raw = listbox.get(indexes[0])
            name = raw[2:]
            kind = "dir" if raw.startswith("📁") else "file"
            return name, kind

        def select_preview(event=None):
            name, kind = selected()
            if not name:
                return

            preview.config(state="normal")
            preview.delete("1.0", "end")

            if kind == "file":
                preview.insert(
                    "1.0",
                    state["cwd"].files[name].content
                )
            else:
                folder = state["cwd"].dirs[name]
                preview.insert(
                    "1.0",
                    f"Klasör: {folder.name}\n"
                    f"Konum: {path_text(folder)}\n\n"
                    f"Alt klasör: {len(folder.dirs)}\n"
                    f"Dosya: {len(folder.files)}"
                )

            preview.config(state="disabled")

        def open_selected(event=None):
            name, kind = selected()
            if not name:
                return

            if kind == "dir":
                state["cwd"] = state["cwd"].dirs[name]
                refresh()
            else:
                if name == "admin":
                    self.open_admin()
                else:
                    self.open_text_file(state["cwd"].files[name])

        def go_up():
            if state["cwd"].parent is not None:
                state["cwd"] = state["cwd"].parent
                refresh()

        def unique_name(container, base, suffix=""):
            candidate = base + suffix
            number = 1
            while candidate in container:
                candidate = f"{base}{number}{suffix}"
                number += 1
            return candidate

        def create_folder():
            name = unique_name(state["cwd"].dirs, "YeniKlasor")
            state["cwd"].dirs[name] = VDir(
                name,
                state["cwd"]
            )
            refresh()

        def create_txt():
            name = unique_name(state["cwd"].files, "YeniMetin", ".txt")
            state["cwd"].files[name] = VFile(
                name,
                ""
            )
            refresh()

        def rename_selected():
            name, kind = selected()
            if not name:
                return

            dialog = tk.Toplevel(win)
            dialog.title("Yeniden Adlandır")
            dialog.geometry("350x150")
            dialog.configure(bg=WINDOW_BG)
            dialog.transient(win)
            dialog.grab_set()

            tk.Label(
                dialog,
                text="Yeni isim:",
                bg=WINDOW_BG,
                font=("Segoe UI", 10, "bold")
            ).pack(pady=(15, 5))

            var = tk.StringVar(value=name)
            entry = tk.Entry(dialog, textvariable=var)
            entry.pack(fill="x", padx=25)
            entry.focus_set()
            entry.select_range(0, "end")

            def apply():
                new_name = var.get().strip()

                if not new_name or new_name == name:
                    dialog.destroy()
                    return

                if "/" in new_name or "\\" in new_name:
                    messagebox.showerror(
                        APP_NAME,
                        "Dosya isminde / veya \\ kullanılamaz.",
                        parent=dialog
                    )
                    return

                if new_name in state["cwd"].dirs or new_name in state["cwd"].files:
                    messagebox.showerror(
                        APP_NAME,
                        "Bu isim zaten kullanılıyor.",
                        parent=dialog
                    )
                    return

                if kind == "dir":
                    obj = state["cwd"].dirs.pop(name)
                    obj.name = new_name
                    state["cwd"].dirs[new_name] = obj
                else:
                    obj = state["cwd"].files.pop(name)
                    obj.name = new_name
                    state["cwd"].files[new_name] = obj

                dialog.destroy()
                refresh()

            tk.Button(
                dialog,
                text="Değiştir",
                command=apply,
                bg=ACCENT,
                fg="white",
                relief="flat"
            ).pack(pady=12)

            entry.bind("<Return>", lambda e: apply())

        def delete_selected():
            name, kind = selected()
            if not name:
                return

            if not messagebox.askyesno(
                APP_NAME,
                f"'{name}' silinsin mi?",
                parent=win
            ):
                return

            if kind == "dir":
                del state["cwd"].dirs[name]
            else:
                del state["cwd"].files[name]

            refresh()

        # Drag-and-drop simulation:
        # Item can be dragged onto a folder row. The item is then moved into that folder.
        def drag_start(event):
            name, kind = selected()
            if name:
                state["drag_name"] = name
                state["drag_kind"] = kind
                listbox.configure(cursor="hand2")

        def drag_move(event):
            if state["drag_name"]:
                try:
                    index = listbox.nearest(event.y)
                    listbox.selection_clear(0, "end")
                    listbox.selection_set(index)
                except tk.TclError:
                    pass

        def drag_end(event):
            dragged = state["drag_name"]
            kind = state["drag_kind"]
            state["drag_name"] = None
            state["drag_kind"] = None
            listbox.configure(cursor="")

            if not dragged:
                return

            target_index = listbox.nearest(event.y)
            if target_index < 0 or target_index >= listbox.size():
                refresh()
                return

            raw_target = listbox.get(target_index)

            if not raw_target.startswith("📁"):
                refresh()
                return

            target_name = raw_target[2:]

            if target_name == dragged:
                refresh()
                return

            target_folder = state["cwd"].dirs.get(target_name)
            if target_folder is None:
                refresh()
                return

            if kind == "dir":
                obj = state["cwd"].dirs.get(dragged)
                if obj is None:
                    refresh()
                    return

                # Prevent moving a folder into itself.
                node = target_folder
                while node is not None:
                    if node is obj:
                        messagebox.showwarning(
                            APP_NAME,
                            "Bir klasör kendisinin içine taşınamaz.",
                            parent=win
                        )
                        refresh()
                        return
                    node = node.parent

                del state["cwd"].dirs[dragged]
                obj.parent = target_folder
                target_folder.dirs[dragged] = obj

            else:
                obj = state["cwd"].files.get(dragged)
                if obj is None:
                    refresh()
                    return

                del state["cwd"].files[dragged]
                target_folder.files[dragged] = obj

            refresh()

        listbox.bind("<<ListboxSelect>>", select_preview)
        listbox.bind("<Double-Button-1>", open_selected)
        listbox.bind("<ButtonPress-1>", drag_start)
        listbox.bind("<B1-Motion>", drag_move)
        listbox.bind("<ButtonRelease-1>", drag_end)

        buttons = tk.Frame(c, bg=WINDOW_BG)
        buttons.pack(fill="x", padx=7, pady=7)

        for label, command in [
            ("⬆ Yukarı", go_up),
            ("📁 Yeni Klasör", create_folder),
            ("📄 Yeni TXT", create_txt),
            ("✎ Yeniden Adlandır", rename_selected),
            ("🗑 Sil", delete_selected),
        ]:
            tk.Button(
                buttons,
                text=label,
                command=command,
                relief="flat",
                padx=7
            ).pack(side="left", padx=2)

        tk.Label(
            c,
            text="İpucu: Bir öğeyi seçip sürükleyerek listedeki bir klasörün üzerine bırak.",
            bg=WINDOW_BG,
            fg="#6b7280",
            font=("Segoe UI", 8)
        ).pack(pady=(0, 5))

        refresh()

    def open_text_file(self, vfile):
        win = InternalWindow(
            self.desktop,
            vfile.name,
            width=500,
            height=380
        )

        # Paneli gerçek masaüstünün ortasına yerleştir.
        self.update_idletasks()
        x = max(
            10,
            (self.desktop.winfo_width() - 500) // 2
        )
        y = max(
            10,
            (self.desktop.winfo_height() - 380) // 2
        )
        win.place(
            x=x, y=y,
            width=500, height=380
        )

        c = win.content

        editor = tk.Text(
            c,
            font=("Segoe UI", 11),
            wrap="word"
        )
        editor.pack(
            expand=True,
            fill="both",
            padx=7,
            pady=7
        )
        editor.insert("1.0", vfile.content)

        def save():
            vfile.content = editor.get(
                "1.0",
                "end-1c"
            )
            win.title_bar.winfo_children()[0].config(
                text=vfile.name
            )

        tk.Button(
            c,
            text="💾 Kaydet",
            command=save,
            bg=ACCENT,
            fg="white",
            relief="flat"
        ).pack(
            side="bottom",
            pady=(0, 7)
        )

    def open_clock_app(self):
        win = self._new_panel("Saat & Takvim", 300, 180)
        c = win.content

        time_label = tk.Label(c, font=("Segoe UI", 24, "bold"), bg=WINDOW_BG)
        time_label.pack(pady=(15, 5))
        date_label = tk.Label(c, font=("Segoe UI", 12), bg=WINDOW_BG)
        date_label.pack()

        def tick():
            if not win.winfo_exists():
                return
            now = datetime.datetime.now()
            time_label.config(text=now.strftime("%H:%M:%S"))
            date_label.config(text=now.strftime("%A, %d %B %Y"))
            win.after(1000, tick)

        tick()

    def open_game(self):
        win = self._new_panel("Sayı Tahmin Oyunu", 300, 230)
        c = win.content

        number = random.randint(1, 100)
        tries = {"count": 0}

        tk.Label(c, text="1-100 arasında bir sayı tuttum!", font=("Segoe UI", 11),
                 bg=WINDOW_BG, wraplength=260).pack(pady=12)

        entry_var = tk.StringVar()
        tk.Entry(c, textvariable=entry_var, font=("Segoe UI", 13),
                  justify="center").pack(pady=5)

        result = tk.Label(c, text="", font=("Segoe UI", 10, "bold"), bg=WINDOW_BG)
        result.pack(pady=8)

        def guess():
            try:
                g = int(entry_var.get())
            except ValueError:
                result.config(text="Lütfen bir sayı girin.")
                return
            tries["count"] += 1
            if g < number:
                result.config(text="Daha büyük bir sayı dene ⬆")
            elif g > number:
                result.config(text="Daha küçük bir sayı dene ⬇")
            else:
                result.config(text=f"Bildin! {tries['count']} denemede.")

        tk.Button(c, text="Tahmin Et", command=guess, bg=ACCENT, fg="white",
                  relief="flat", padx=10, pady=3).pack()

    def open_admin(self):
        d = tk.Toplevel(self); d.title("admin"); d.geometry("360x190"); d.resizable(False,False); d.configure(bg=WINDOW_BG); d.transient(self); d.grab_set()
        tk.Label(d,text="🔐 admin",font=("Segoe UI",18,"bold"),bg=WINDOW_BG).pack(pady=(18,5))
        tk.Label(d,text="Şifre:",bg=WINDOW_BG).pack()
        v=tk.StringVar(); e=tk.Entry(d,textvariable=v,show="•",font=("Segoe UI",13),justify="center"); e.pack(padx=35,pady=8,fill="x"); e.focus_set()
        st=tk.Label(d,text="",bg=WINDOW_BG,fg="#dc2626"); st.pack()
        def check():
            if v.get()=="00362": d.destroy(); self._open_admin_panel()
            else: st.config(text="Yanlış şifre!"); v.set("")
        tk.Button(d,text="Aç",command=check,bg=ACCENT,fg="white",relief="flat",padx=25).pack(pady=8); e.bind("<Return>",lambda _:check())

    def _open_admin_panel(self):
        w=self._new_panel("admin — Yönetici Testleri",390,260); c=w.content
        tk.Label(c,text="Yönetici Test Paneli",font=("Segoe UI",16,"bold"),bg=WINDOW_BG).pack(pady=(18,8))
        tk.Button(c,text="🟦 Mavi Ekran Testi",command=self._simulate_bsod,bg="#2563eb",fg="white",relief="flat",font=("Segoe UI",11,"bold"),pady=8).pack(fill="x",padx=35,pady=10)
        tk.Button(c,text="🛡 Güvenli Modda Yeniden Başlat",command=self._restart_safe_mode,bg="#374151",fg="white",relief="flat",font=("Segoe UI",11,"bold"),pady=8).pack(fill="x",padx=35,pady=5)

    def _sound(self):
        try:
            if winsound: winsound.Beep(650,140)
            else: self.bell()
        except Exception: self.bell()

    def _restart_safe_mode(self):
        self._safe_mode=True; self._fade_black(self._safe_boot)

    def _fade_black(self,done):
        o=tk.Frame(self,bg="#18212b"); o.place(x=0,y=0,relwidth=1,relheight=1); o.lift(); shades=["#18212b","#10161d","#080c10","#030405","#000000"]
        def step(i=0):
            self._sound()
            if i>=len(shades):
                o.destroy()
                self.after(600,done)
                return
            o.config(bg=shades[i]); self.after(120,lambda:step(i+1))
        step()

    def _safe_boot(self):
        for w in list(self.winfo_children()):
            try: w.destroy()
            except: pass
        self._show_boot_screen()

    def _show_safe_mode_label(self):
        tk.Label(self,text="GÜVENLİ MOD",bg="#111827",fg="white",font=("Segoe UI",10,"bold"),padx=8,pady=4).place(relx=1,x=-10,y=10,anchor="ne")

    def _simulate_bsod(self):
        if self._safe_mode:
            messagebox.showinfo(APP_NAME,"Güvenli modda mavi ekran testi devre dışı.",parent=self); return
        f=tk.Frame(self,bg="#0078d7"); f.place(x=0,y=0,relwidth=1,relheight=1); f.lift()
        tk.Label(f,text=":(",bg="#0078d7",fg="white",font=("Segoe UI",72)).pack(anchor="w",padx=80,pady=(90,10))
        tk.Label(f,text="X OS bir sorunla karşılaştı ve yeniden başlatılması gerekiyor.",bg="#0078d7",fg="white",font=("Segoe UI",18),wraplength=780,justify="left").pack(anchor="w",padx=90)
        p=tk.Label(f,text="0% tamamlandı",bg="#0078d7",fg="white",font=("Segoe UI",12)); p.pack(anchor="w",padx=90,pady=25); self._sound()
        def go(n=0):
            p.config(text=f"{n}% tamamlandı")
            if n>=100: self.after(1000,lambda:self._bsod_restart(f))
            else: self.after(40,lambda:go(min(100,n+random.randint(4,9))))
        go()

    def _bsod_restart(self,f):
        f.destroy(); self._fade_black(self._normal_restart)

    def _normal_restart(self):
        self._safe_mode=False; self._show_boot_screen()

    def destroy(self):
        try:
            self._stop_music()
        except Exception:
            pass
        return super().destroy()

    # ====================================================================
    # ADMIN DOSYASI / TEST PANELİ
    # ====================================================================

    def open_admin(self):
        dialog = tk.Toplevel(self)
        dialog.title("admin")
        dialog.geometry("360x210")
        dialog.resizable(False, False)
        dialog.configure(bg=WINDOW_BG)
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(
            dialog, text="🔐 admin",
            font=("Segoe UI", 18, "bold"),
            bg=WINDOW_BG
        ).pack(pady=(20, 5))

        tk.Label(
            dialog,
            text="Dosyayı açmak için şifreyi gir:",
            bg=WINDOW_BG
        ).pack(pady=5)

        password = tk.StringVar()

        entry = tk.Entry(
            dialog,
            textvariable=password,
            show="•",
            font=("Segoe UI", 14),
            justify="center"
        )
        entry.pack(padx=40, pady=8, fill="x")

        status = tk.Label(
            dialog, text="", bg=WINDOW_BG, fg="#dc2626"
        )
        status.pack()

        def check_password():
            if password.get() == "00362":
                dialog.destroy()
                self.open_admin_panel()
            else:
                status.config(text="Yanlış şifre!")
                password.set("")
                entry.focus_set()

        tk.Button(
            dialog, text="Aç",
            command=check_password,
            bg=ACCENT, fg="white",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=25, pady=5
        ).pack(pady=8)

        entry.bind("<Return>", lambda e: check_password())
        entry.focus_set()

    def open_admin_panel(self):
        win = self._new_panel(
            "admin - Yönetici Testleri", 400, 280
        )
        c = win.content

        tk.Label(
            c,
            text="Yönetici Test Paneli",
            font=("Segoe UI", 16, "bold"),
            bg=WINDOW_BG
        ).pack(pady=(20, 5))

        tk.Label(
            c,
            text="X OS sistem testleri",
            bg=WINDOW_BG,
            fg="#6b7280"
        ).pack()

        tk.Button(
            c,
            text="🟦 Mavi Ekran Testi",
            command=self.simulate_bsod,
            bg="#2563eb", fg="white",
            relief="flat",
            font=("Segoe UI", 11, "bold"),
            pady=10
        ).pack(fill="x", padx=35, pady=(20, 8))

        tk.Button(
            c,
            text="🛡 Güvenli Modda Yeniden Başlat",
            command=self.restart_safe_mode,
            bg="#374151", fg="white",
            relief="flat",
            font=("Segoe UI", 11, "bold"),
            pady=10
        ).pack(fill="x", padx=35)

    def play_system_sound(self):
        try:
            import winsound
            winsound.Beep(600, 150)
            self.after(120, lambda: winsound.Beep(800, 150))
        except Exception:
            try:
                self.bell()
            except Exception:
                pass

    def fade_to_black(self, callback):
        overlay = tk.Frame(self, bg="black")
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        overlay.lift()

        shades = [
            "#202020", "#181818", "#101010",
            "#080808", "#040404", "#000000"
        ]

        def fade(step=0):
            if step >= len(shades):
                self.after(600, callback)
                return

            overlay.configure(bg=shades[step])
            self.play_system_sound()

            self.after(
                120,
                lambda: fade(step + 1)
            )

        fade()

    def simulate_bsod(self):
        if self.safe_mode:
            messagebox.showinfo(
                APP_NAME,
                "Güvenli modda mavi ekran testi kullanılamaz."
            )
            return

        if hasattr(self, "desktop"):
            self.desktop.place_forget()

        if hasattr(self, "taskbar"):
            self.taskbar.place_forget()

        bsod = tk.Frame(self, bg="#0078D7")
        bsod.place(x=0, y=0, relwidth=1, relheight=1)
        bsod.lift()

        tk.Label(
            bsod,
            text=":(",
            bg="#0078D7",
            fg="white",
            font=("Segoe UI", 72)
        ).pack(anchor="w", padx=80, pady=(80, 10))

        tk.Label(
            bsod,
            text=(
                "X OS bir sorunla karşılaştı "
                "ve yeniden başlatılması gerekiyor."
            ),
            bg="#0078D7",
            fg="white",
            font=("Segoe UI", 18),
            wraplength=750,
            justify="left"
        ).pack(anchor="w", padx=90)

        progress = tk.Label(
            bsod,
            text="0% tamamlandı",
            bg="#0078D7",
            fg="white",
            font=("Segoe UI", 12)
        )
        progress.pack(anchor="w", padx=90, pady=25)

        self.play_system_sound()

        def update_progress(value=0):
            if value >= 100:
                progress.config(text="100% tamamlandı")
                self.after(
                    1000,
                    lambda: restart(bsod)
                )
                return

            progress.config(
                text=f"{value}% tamamlandı"
            )

            self.after(
                50,
                lambda: update_progress(
                    min(100, value + random.randint(4, 9))
                )
            )

        def restart(frame):
            frame.destroy()
            self.configure(bg=BOOT_BG)
            self._show_boot_screen()

        update_progress()

    def restart_safe_mode(self):
        self.safe_mode_after_boot = True
        self.fade_to_black(self.safe_mode_boot)

    def safe_mode_boot(self):
        if hasattr(self, "desktop"):
            try:
                self.desktop.destroy()
            except Exception:
                pass

        if hasattr(self, "taskbar"):
            try:
                self.taskbar.destroy()
            except Exception:
                pass

        self.configure(bg=BOOT_BG)
        self._show_boot_screen()

    def show_safe_mode_label(self):
        self.safe_mode = True

        label = tk.Label(
            self,
            text="GÜVENLİ MOD",
            bg="#111827",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=10, pady=5
        )

        label.place(
            relx=1.0,
            x=-10,
            y=10,
            anchor="ne"
        )
        label.lift()

    # ====================================================================
    # YILAN + UZUN LABİRENT
    # ====================================================================

    def open_snake_maze(self):
        win = self._new_panel("🐍 Yılan + Labirent", 760, 590)
        self.update_idletasks()
        win.place(
            x=max(10, (self.desktop.winfo_width()-760)//2),
            y=max(10, (self.desktop.winfo_height()-590)//2),
            width=760, height=590
        )

        c = win.content
        info = tk.Frame(c, bg=WINDOW_BG)
        info.pack(fill="x", padx=8, pady=6)

        score = tk.StringVar(value="Skor: 0")
        level = tk.StringVar(value="Labirent: 1")
        status = tk.StringVar(value="Ok tuşları / WASD ile hareket et")

        tk.Label(info, textvariable=score, bg=WINDOW_BG,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=8)
        tk.Label(info, textvariable=level, bg=WINDOW_BG,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=8)
        tk.Label(info, textvariable=status, bg=WINDOW_BG,
                 fg="#6b7280").pack(side="right", padx=8)

        canvas = tk.Canvas(c, bg="#0b1220", highlightthickness=1,
                           highlightbackground="#374151")
        canvas.pack(expand=True, fill="both", padx=8, pady=(0, 8))

        cols, rows, cell = 31, 21, 22
        canvas.config(width=cols*cell, height=rows*cell)

        g = {
            "snake": [(2, rows//2), (1, rows//2)],
            "dir": (1, 0), "next": (1, 0),
            "food": (cols-3, rows//2),
            "score": 0, "level": 1, "running": True,
            "after": None, "walls": set()
        }

        def make_maze(lvl):
            walls = set()
            for x in range(cols):
                walls.update(((x, 0), (x, rows-1)))
            for y in range(rows):
                walls.update(((0, y), (cols-1, y)))

            spacing = max(4, 6-min(lvl, 2))
            for x in range(5, cols-2, spacing):
                gap = 2 + ((x + lvl*3) % (rows-5))
                for y in range(1, rows-1):
                    if y not in (gap, gap+1):
                        walls.add((x, y))

            for y in range(5, rows-3, 6):
                gap = 3 + ((y*2 + lvl) % (cols-7))
                for x in range(1, cols-1):
                    if x not in (gap, gap+1):
                        walls.add((x, y))

            walls -= set(g["snake"])
            return walls

        def free(p):
            return (0 <= p[0] < cols and 0 <= p[1] < rows
                    and p not in g["walls"])

        def new_food():
            import random
            free_cells = [
                (x, y) for y in range(1, rows-1)
                for x in range(1, cols-1)
                if (x, y) not in g["walls"] and (x, y) not in g["snake"]
            ]
            if free_cells:
                g["food"] = random.choice(free_cells)

        def draw():
            canvas.delete("all")
            for x, y in g["walls"]:
                canvas.create_rectangle(
                    x*cell, y*cell, (x+1)*cell, (y+1)*cell,
                    fill="#334155", outline="#475569")
            x, y = g["food"]
            canvas.create_oval(x*cell+4, y*cell+4,
                               (x+1)*cell-4, (y+1)*cell-4,
                               fill="#f59e0b", outline="")
            for i, (x, y) in enumerate(g["snake"]):
                canvas.create_rectangle(
                    x*cell+2, y*cell+2, (x+1)*cell-2, (y+1)*cell-2,
                    fill="#22c55e" if i == 0 else "#16a34a", outline="")
            score.set(f"Skor: {g['score']}")
            level.set(f"Labirent: {g['level']}")

        def game_over(msg):
            g["running"] = False
            if g["after"]:
                try: win.after_cancel(g["after"])
                except tk.TclError: pass
            status.set(msg)

            box = tk.Frame(canvas, bg="#111827")
            box.place(relx=.5, rely=.5, anchor="center", width=330, height=180)
            tk.Label(box, text="OYUN BİTTİ", bg="#111827", fg="white",
                     font=("Segoe UI", 20, "bold")).pack(pady=(25, 8))
            tk.Label(box, text=f"Skor: {g['score']}", bg="#111827",
                     fg="#cbd5e1").pack()

            def again():
                box.destroy()
                g.update({
                    "snake": [(2, rows//2), (1, rows//2)],
                    "dir": (1,0), "next": (1,0),
                    "score": 0, "level": 1, "running": True
                })
                g["walls"] = make_maze(1)
                new_food()
                status.set("Ok tuşları / WASD ile hareket et")
                draw()
                tick()

            tk.Button(box, text="Tekrar Oyna", command=again,
                      bg=ACCENT, fg="white", relief="flat",
                      padx=20, pady=8).pack(pady=18)

        def tick():
            if not g["running"]: return
            dx, dy = g["next"]
            g["dir"] = (dx, dy)
            hx, hy = g["snake"][0]
            head = (hx+dx, hy+dy)

            if not free(head) or head in g["snake"][:-1]:
                game_over("Duvara veya kendine çarptın!")
                return

            g["snake"].insert(0, head)
            if head == g["food"]:
                g["score"] += 10
                new_level = g["score"]//50 + 1
                if new_level != g["level"]:
                    g["level"] = new_level
                    g["walls"] = make_maze(new_level)
                    g["walls"] -= set(g["snake"])
                    status.set(f"Seviye {new_level}! Labirent uzadı.")
                new_food()
            else:
                g["snake"].pop()

            draw()
            delay = max(65, 135-(g["level"]-1)*8)
            g["after"] = win.after(delay, tick)

        def key(event):
            dirs = {
                "up": (0,-1), "w": (0,-1),
                "down": (0,1), "s": (0,1),
                "left": (-1,0), "a": (-1,0),
                "right": (1,0), "d": (1,0)
            }
            k = event.keysym.lower()
            if k in dirs:
                nd = dirs[k]
                if nd != (-g["dir"][0], -g["dir"][1]):
                    g["next"] = nd
                return "break"

        g["walls"] = make_maze(1)
        new_food()
        draw()
        win.bind_all("<KeyPress>", key)
        win.focus_set()
        tick()

        old_close = win.animate_close
        def close_game(*args, **kwargs):
            g["running"] = False
            if g["after"]:
                try: win.after_cancel(g["after"])
                except tk.TclError: pass
            try: win.unbind_all("<KeyPress>")
            except tk.TclError: pass
            return old_close(*args, **kwargs)
        win.animate_close = close_game

    # ====================================================================
    # XUPDATETOOL
    # ====================================================================

    # ====================================================================
    # XUPDATETOOL - GITHUB RELEASES
    # ====================================================================

    def open_xupdate_tool(self):
        win = self._new_panel("XUpdateTool", 560, 430)
        self.update_idletasks()
        win.place(
            x=max(10, (self.desktop.winfo_width() - 560) // 2),
            y=max(10, (self.desktop.winfo_height() - 430) // 2),
            width=560,
            height=430
        )

        c = win.content

        tk.Label(
            c, text="🔄 XUpdateTool",
            bg=WINDOW_BG,
            font=("Segoe UI", 20, "bold")
        ).pack(pady=(25, 4))

        tk.Label(
            c,
            text="GitHub Releases üzerinden X OS güncellemelerini kontrol eder.",
            bg=WINDOW_BG,
            fg="#6b7280"
        ).pack()

        version_label = tk.Label(
            c,
            text=f"Yüklü sürüm: v{XOS_VERSION}",
            bg=WINDOW_BG,
            font=("Segoe UI", 10, "bold")
        )
        version_label.pack(pady=(15, 5))

        status = tk.Label(
            c,
            text="Kontrol edilmeye hazır.",
            bg=WINDOW_BG,
            fg="#374151",
            wraplength=480,
            justify="center"
        )
        status.pack(pady=15)

        result = tk.Text(
            c,
            height=7,
            width=58,
            state="disabled",
            wrap="word"
        )
        result.pack(padx=15, pady=5)

        def show_result(text_value):
            result.config(state="normal")
            result.delete("1.0", "end")
            result.insert("1.0", text_value)
            result.config(state="disabled")

        def check_github():
            check_btn.config(state="disabled")
            status.config(text="GitHub'da güncelleme aranıyor...")
            show_result("Bağlanıyor...")
            win.update_idletasks()

            def worker():
                import urllib.request
                import json
                import threading

                owner = XOS_GITHUB_OWNER
                repo = XOS_GITHUB_REPO

                if (
                    not owner or owner == "YOUR_GITHUB_USERNAME" or
                    not repo or repo == "YOUR_XOS_REPOSITORY"
                ):
                    self.after(0, lambda: (
                        check_btn.config(state="normal"),
                        status.config(text="GitHub deposu ayarlanmamış."),
                        show_result(
                            "XOS_GITHUB_OWNER ve XOS_GITHUB_REPO "
                            "değerlerini kendi GitHub depona göre değiştir."
                        )
                    ))
                    return

                url = (
                    f"https://api.github.com/repos/"
                    f"{owner}/{repo}/releases/latest"
                )

                try:
                    request = urllib.request.Request(
                        url,
                        headers={
                            "Accept": "application/vnd.github+json",
                            "User-Agent": "XUpdateTool-XOS"
                        }
                    )

                    with urllib.request.urlopen(
                        request, timeout=10
                    ) as response:
                        data = json.loads(
                            response.read().decode("utf-8")
                        )

                    tag = str(data.get("tag_name", "")).strip()
                    latest = tag.lstrip("vV")
                    notes = str(
                        data.get("body", "")
                    ).strip() or "Değişiklik notu yok."

                    release_url = str(
                        data.get("html_url", "")
                    ).strip()

                    assets = data.get("assets", [])
                    asset_url = ""

                    for asset in assets:
                        if asset.get("name") == XOS_RELEASE_ASSET:
                            asset_url = str(
                                asset.get("browser_download_url", "")
                            )
                            break

                    def compare_versions(a, b):
                        try:
                            pa = tuple(
                                int(x)
                                for x in a.split(".")
                                if x.isdigit()
                            )
                            pb = tuple(
                                int(x)
                                for x in b.split(".")
                                if x.isdigit()
                            )
                            n = max(len(pa), len(pb))
                            return (
                                pa + (0,) * (n-len(pa))
                            ) < (
                                pb + (0,) * (n-len(pb))
                            )
                        except Exception:
                            return a != b

                    def done():
                        check_btn.config(state="normal")

                        if not latest:
                            status.config(
                                text="GitHub sürüm bilgisi okunamadı."
                            )
                            return

                        if compare_versions(XOS_VERSION, latest):
                            status.config(
                                text=f"🆕 Yeni sürüm bulundu: v{latest}"
                            )

                            text_value = (
                                f"Mevcut sürüm: v{XOS_VERSION}\n"
                                f"Yeni sürüm: v{latest}\n\n"
                                f"Değişiklikler:\n{notes}"
                            )
                            show_result(text_value)

                            if asset_url:
                                def download_release():
                                    import webbrowser
                                    webbrowser.open(asset_url)

                                tk.Button(
                                    c,
                                    text="⬇ X OS Güncellemesini İndir",
                                    command=download_release,
                                    bg=ACCENT,
                                    fg="white",
                                    relief="flat",
                                    padx=18,
                                    pady=9
                                ).pack(pady=8)
                            else:
                                tk.Button(
                                    c,
                                    text="🌐 GitHub Release'ı Aç",
                                    command=lambda: __import__(
                                        "webbrowser"
                                    ).open(release_url),
                                    bg="#374151",
                                    fg="white",
                                    relief="flat",
                                    padx=18,
                                    pady=9
                                ).pack(pady=8)

                        else:
                            status.config(
                                text=f"✓ X OS güncel — v{XOS_VERSION}"
                            )
                            show_result(
                                f"GitHub'daki son yayın: v{latest}\n\n"
                                f"Yeni güncelleme bulunamadı."
                            )

                    self.after(0, done)

                except Exception as exc:
                    self.after(0, lambda: (
                        check_btn.config(state="normal"),
                        status.config(text="Güncelleme kontrolü başarısız."),
                        show_result(
                            "GitHub'a bağlanılamadı.\n\n"
                            f"Hata: {exc}"
                        )
                    ))

            import threading
            threading.Thread(
                target=worker,
                daemon=True
            ).start()

        check_btn = tk.Button(
            c,
            text="🔎 Güncellemeleri Kontrol Et",
            command=check_github,
            bg=ACCENT,
            fg="white",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=18,
            pady=9
        )
        check_btn.pack(pady=8)

        tk.Label(
            c,
            text=f"GitHub: {XOS_GITHUB_OWNER}/{XOS_GITHUB_REPO}",
            bg=WINDOW_BG,
            fg="#9ca3af",
            font=("Segoe UI", 8)
        ).pack(pady=4)

    # ====================================================================
    # MÜZİK ÇALAR
    # ====================================================================

    def open_music_player(self):
        win = self._new_panel("Müzik Çalar", 430, 270)

        self.update_idletasks()
        x = max(10, (self.desktop.winfo_width() - 430) // 2)
        y = max(10, (self.desktop.winfo_height() - 270) // 2)
        win.place(x=x, y=y, width=430, height=270)

        c = win.content

        tk.Label(
            c,
            text="🎵 Müzik Çalar",
            bg=WINDOW_BG,
            font=("Segoe UI", 18, "bold")
        ).pack(pady=(25, 8))

        tk.Label(
            c,
            text="ALTERED OBSIDIAN",
            bg=WINDOW_BG,
            fg="#6b7280",
            font=("Segoe UI", 12)
        ).pack(pady=5)

        status = tk.Label(
            c,
            text="Hazır",
            bg=WINDOW_BG,
            fg="#374151"
        )
        status.pack(pady=8)

        controls = tk.Frame(c, bg=WINDOW_BG)
        controls.pack(pady=10)

        def play():
            self._play_altered_obsidian()
            status.config(text="▶ Çalıyor: ALTERED OBSIDIAN")

        def stop():
            self._stop_music()
            status.config(text="■ Durduruldu")

        tk.Button(
            controls,
            text="▶ Çal",
            command=play,
            bg=ACCENT,
            fg="white",
            relief="flat",
            padx=20,
            pady=8
        ).pack(side="left", padx=5)

        tk.Button(
            controls,
            text="■ Durdur",
            command=stop,
            bg="#374151",
            fg="white",
            relief="flat",
            padx=20,
            pady=8
        ).pack(side="left", padx=5)

        tk.Label(
            c,
            text="Not: Şarkı dosyası X OS klasöründe ALTERED OBSIDIAN adıyla bulunmalıdır.",
            bg=WINDOW_BG,
            fg="#9ca3af",
            wraplength=360,
            justify="center"
        ).pack(pady=10)

    def _find_altered_obsidian(self):
        base = Path(__file__).resolve().parent
        names = [
            "ALTERED OBSIDIAN.mp3",
            "ALTERED OBSIDIAN.wav",
            "ALTERED OBSIDIAN.ogg",
            "altered obsidian.mp3",
            "altered_obsidian.mp3",
        ]

        for name in names:
            p = base / name
            if p.exists():
                return p

        # Also check a Music folder beside the program.
        music_dir = base / "Music"
        for name in names:
            p = music_dir / name
            if p.exists():
                return p

        return None

    def _play_altered_obsidian(self):
        path = self._find_altered_obsidian()

        if path is None:
            messagebox.showwarning(
                APP_NAME,
                "ALTERED OBSIDIAN bulunamadı.\n\n"
                "Müzik dosyasını programın yanına "
                "'ALTERED OBSIDIAN.mp3' adıyla koy."
            )
            return

        # MP3'ü Windows'un sistem sesi olarak çalmıyoruz.
        # pygame ile doğrudan müzik dosyasını oynatıyoruz.
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init()

            pygame.mixer.music.stop()
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play(-1)

            self.music_player_process = pygame
            self.music_playing = True
            self.music_file = path

        except ImportError:
            messagebox.showerror(
                APP_NAME,
                "Müzik çalar için pygame gerekli.\n\n"
                "Terminalde şunu çalıştır:\n\n"
                "python -m pip install pygame"
            )
        except Exception as exc:
            messagebox.showerror(
                APP_NAME,
                f"ALTERED OBSIDIAN çalınamadı:\n{exc}"
            )

    def _stop_music(self):
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

        self.music_player_process = None
        self.music_playing = False
        self.music_file = None

    def open_sysinfo(self):
        win = self._new_panel("Sistem Bilgisi", 300, 190)
        c = win.content

        info = (
            f"İşletim Sistemi: {APP_NAME} v{VERSION}\n\n"
            f"Arayüz: Tkinter (panel modu)\n"
        )
        tk.Label(c, text=info, font=("Segoe UI", 10), bg=WINDOW_BG,
                 justify="left", anchor="w").pack(padx=12, pady=12, fill="both")


if __name__ == "__main__":
    app = XOS()
    app.mainloop()
