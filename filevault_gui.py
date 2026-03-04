#!/usr/bin/env python3
"""
FileVault GUI v4.0 — CustomTkinter frontend
Calls filevault.run_job(cfg) directly — same engine as CLI and YAML.
"""

import datetime
import json
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

try:
    from tkinter import filedialog, messagebox

    import customtkinter as ctk
except ImportError:
    print("pip install customtkinter")
    sys.exit(1)

# Ensure engine importable
sys.path.insert(0, str(Path(__file__).parent))
# import filevault as fv
import filevault as fv

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT = "#00d4ff"
GREEN = "#00ff88"
RED = "#ff4444"
ORANGE = "#ff9944"
YELLOW = "#ffdd44"
BG = "#0d0d0d"
PANEL = "#141414"
CARD = "#1a1a2e"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
class StatCard(ctk.CTkFrame):
    def __init__(self, master, label, color=ACCENT, **kw):
        super().__init__(master, fg_color=CARD, corner_radius=10, **kw)
        self._v = ctk.StringVar(value="—")
        ctk.CTkLabel(
            self,
            textvariable=self._v,
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=color,
        ).pack(pady=(12, 2))
        ctk.CTkLabel(
            self, text=label, font=ctk.CTkFont(size=10), text_color="#777"
        ).pack(pady=(0, 10))

    def set(self, v):
        self._v.set(str(v))


def section(parent, text):
    ctk.CTkLabel(
        parent, text=text, font=ctk.CTkFont(size=13, weight="bold"), text_color=ACCENT
    ).pack(anchor="w", padx=24, pady=(16, 4))


def sep(parent):
    ctk.CTkFrame(parent, height=1, fg_color="#222").pack(fill="x", padx=16, pady=4)


# ─────────────────────────────────────────────────────────────────────────────
# GUI LOGGER HANDLER
# ─────────────────────────────────────────────────────────────────────────────
import logging


class GUILogHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self._cb = callback
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    def emit(self, record):
        self._cb(self.format(record))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self, source_arg: str = ""):
        super().__init__()
        self.title("🗄️ FileVault v4.0")
        self.geometry("1220x820")
        self.minsize(1050, 700)
        self.configure(fg_color=BG)
        self._log_lines = []
        self._running = False
        self._report = {}
        self._gui_handler = GUILogHandler(self._append_log)
        fv.log.addHandler(self._gui_handler)
        self._build()
        if source_arg:
            self._src_var.set(source_arg)

    # ────────────────────────────── BUILD ─────────────────────────────────────
    def _build(self):
        # Sidebar
        sb = ctk.CTkFrame(self, width=230, fg_color=PANEL, corner_radius=0)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        ctk.CTkLabel(
            sb,
            text="🗄️ FileVault",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=ACCENT,
        ).pack(pady=(22, 2))
        ctk.CTkLabel(
            sb,
            text="v4.0 • Smart Organizer",
            font=ctk.CTkFont(size=10),
            text_color="#555",
        ).pack(pady=(0, 16))

        self._pages = {}
        pages = [
            ("⚙️  Configure", self._pg_configure),
            ("▶️  Run", self._pg_run),
            ("📋  Log", self._pg_log),
            ("📊  Reports", self._pg_reports),
            ("↩️  Undo", self._pg_undo),
            ("🛠️  Settings", self._pg_settings),
            ("ℹ️  About", self._pg_about),
        ]

        for lbl, builder in pages:
            key = lbl.split()[1].lower().strip("️")
            self._pages[key] = None
            btn = ctk.CTkButton(
                sb,
                text=lbl,
                anchor="w",
                height=38,
                fg_color="transparent",
                hover_color="#1e1e3a",
                text_color="#ccc",
                font=ctk.CTkFont(size=12),
                command=lambda k=key, b=builder: self._show(k, b),
            )
            btn.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(sb, text="", fg_color="transparent").pack(expand=True)

        # Content frame
        self._content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)
        self._current_page = None

        self._show("configure", self._pg_configure)

    def _show(self, key, builder):
        if self._current_page:
            self._current_page.pack_forget()
        if self._pages.get(key) is None:
            self._pages[key] = builder()
        self._pages[key].pack(fill="both", expand=True)
        self._current_page = self._pages[key]

    # ─────────────────────────────────────────────────────────────────────────
    # PAGE: CONFIGURE
    # ─────────────────────────────────────────────────────────────────────────
    def _pg_configure(self):
        page = ctk.CTkScrollableFrame(self._content, fg_color=BG)
        ctk.CTkLabel(
            page,
            text="⚙️  Configure Job",
            font=ctk.CTkFont(size=21, weight="bold"),
            text_color=ACCENT,
        ).pack(anchor="w", padx=24, pady=(22, 4))

        # Paths
        section(page, "📁  Paths")
        self._src_var = ctk.StringVar()
        self._tgt_var = ctk.StringVar()
        self._path_row(
            page, "Source Folder", self._src_var, lambda: self._pick(self._src_var)
        )
        self._path_row(
            page, "Target Folder", self._tgt_var, lambda: self._pick(self._tgt_var)
        )

        # Move Mode
        section(page, "📦  Move Mode")
        self._move_mode = ctk.StringVar(value="all")
        for v, t in [
            ("all", "Move ALL files — source fully emptied"),
            (
                "unique",
                "Move UNIQUE files only — dupes shredded in-place, NOT copied to target",
            ),
            ("dupes", "Move DUPLICATE files only — unique files stay in source"),
        ]:
            ctk.CTkRadioButton(page, text=t, variable=self._move_mode, value=v).pack(
                anchor="w", padx=32, pady=2
            )

        # Output Structure
        section(page, "📂  Output Folder Structure")
        self._use_sf = ctk.BooleanVar(value=True)
        self._sf_mode = ctk.StringVar(value="unique_dupes")
        ctk.CTkCheckBox(
            page, text="Create sub-folders in target", variable=self._use_sf
        ).pack(anchor="w", padx=32, pady=3)
        sf_f = ctk.CTkFrame(page, fg_color="transparent")
        sf_f.pack(anchor="w", padx=48)
        for v, t in [
            ("unique_dupes", "unique/ + duplicates/"),
            ("by_type", "by file type: pdf/ images/ office/ other/"),
            ("flat", "flat — all files in target root, no sub-folders"),
        ]:
            ctk.CTkRadioButton(sf_f, text=t, variable=self._sf_mode, value=v).pack(
                anchor="w", pady=2
            )

        # Rename Options
        section(page, "✏️  Rename Options")
        self._r_folder = ctk.BooleanVar(value=True)
        self._r_meta = ctk.BooleanVar(value=True)
        self._r_date = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            page,
            text="Rename solo file to match parent folder name",
            variable=self._r_folder,
        ).pack(anchor="w", padx=32, pady=2)
        ctk.CTkCheckBox(
            page,
            text="Smart rename PDFs / eBooks / Office docs from embedded metadata",
            variable=self._r_meta,
        ).pack(anchor="w", padx=32, pady=2)
        ctk.CTkCheckBox(
            page,
            text="Prefix image filenames with EXIF date  (e.g. 2024-07-14_photo.jpg)",
            variable=self._r_date,
        ).pack(anchor="w", padx=32, pady=2)

        # EXIF Editor
        section(page, "🔬  EXIF Metadata Editor (images only)")
        self._exif_rm_gps = ctk.BooleanVar(value=False)
        self._exif_rm_device = ctk.BooleanVar(value=False)
        self._exif_rm_date = ctk.BooleanVar(value=False)
        self._exif_set_author = ctk.StringVar(value="")
        self._exif_set_desc = ctk.StringVar(value="")
        ctk.CTkCheckBox(
            page, text="Remove GPS coordinates", variable=self._exif_rm_gps
        ).pack(anchor="w", padx=32, pady=2)
        ctk.CTkCheckBox(
            page,
            text="Remove device info (Make/Model/Software)",
            variable=self._exif_rm_device,
        ).pack(anchor="w", padx=32, pady=2)
        ctk.CTkCheckBox(
            page, text="Remove DateTime fields", variable=self._exif_rm_date
        ).pack(anchor="w", padx=32, pady=2)
        r = ctk.CTkFrame(page, fg_color="transparent")
        r.pack(anchor="w", padx=32, pady=2)
        ctk.CTkLabel(r, text="Set Author (blank = keep):").pack(side="left")
        ctk.CTkEntry(r, textvariable=self._exif_set_author, width=260).pack(
            side="left", padx=8
        )
        r2 = ctk.CTkFrame(page, fg_color="transparent")
        r2.pack(anchor="w", padx=32, pady=2)
        ctk.CTkLabel(r2, text="Set Description (blank = keep):").pack(side="left")
        ctk.CTkEntry(r2, textvariable=self._exif_set_desc, width=260).pack(
            side="left", padx=8
        )

        # Shred
        section(page, "🔒  Secure Shred")
        self._shrd_dupes = ctk.BooleanVar(value=True)
        self._shrd_all = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            page,
            text="Securely shred duplicate source files (DoD 7-pass)",
            variable=self._shrd_dupes,
        ).pack(anchor="w", padx=32, pady=2)
        ctk.CTkCheckBox(
            page,
            text="Securely shred ALL source files after copy (maximum privacy)",
            variable=self._shrd_all,
        ).pack(anchor="w", padx=32, pady=2)
        pr = ctk.CTkFrame(page, fg_color="transparent")
        pr.pack(anchor="w", padx=32, pady=4)
        ctk.CTkLabel(pr, text="Passes:").pack(side="left")
        self._passes = ctk.IntVar(value=7)
        sl = ctk.CTkSlider(
            pr, from_=1, to=35, variable=self._passes, width=180, number_of_steps=34
        )
        sl.pack(side="left", padx=8)
        pl = ctk.CTkLabel(pr, text="7", text_color=ACCENT, width=30)
        pl.pack(side="left")
        self._passes.trace_add(
            "write", lambda *_: pl.configure(text=str(self._passes.get()))
        )

        # Exclude
        section(page, "🚫  Exclude Patterns (comma-separated)")
        self._excl = ctk.StringVar(
            value="*.tmp, *.DS_Store, Thumbs.db, desktop.ini, *.log"
        )
        ctk.CTkEntry(page, textvariable=self._excl, width=520).pack(
            anchor="w", padx=32, pady=4
        )

        # Performance
        section(page, "⚡  Performance")
        wr = ctk.CTkFrame(page, fg_color="transparent")
        wr.pack(anchor="w", padx=32, pady=4)
        ctk.CTkLabel(wr, text="Workers:").pack(side="left")
        self._workers = ctk.IntVar(value=8)
        ws = ctk.CTkSlider(
            wr, from_=1, to=32, variable=self._workers, width=180, number_of_steps=31
        )
        ws.pack(side="left", padx=8)
        wl = ctk.CTkLabel(wr, text="8", text_color=ACCENT, width=30)
        wl.pack(side="left")
        self._workers.trace_add(
            "write", lambda *_: wl.configure(text=str(self._workers.get()))
        )
        self._quick = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            page,
            text="Quick-scan mode (hash first 4MB only — faster, not 100% exact)",
            variable=self._quick,
        ).pack(anchor="w", padx=32, pady=2)

        # Plugin dir
        section(page, "🔌  Plugin Directory (optional)")
        pd_r = ctk.CTkFrame(page, fg_color="transparent")
        pd_r.pack(anchor="w", padx=32, pady=4)
        self._plugin_dir = ctk.StringVar()
        ctk.CTkEntry(pd_r, textvariable=self._plugin_dir, width=360).pack(side="left")
        ctk.CTkButton(
            pd_r,
            text="Browse",
            width=80,
            command=lambda: self._plugin_dir.set(
                filedialog.askdirectory() or self._plugin_dir.get()
            ),
        ).pack(side="left", padx=8)

        # Reports
        section(page, "📊  Reports")
        self._rj = ctk.BooleanVar(value=True)
        self._rc = ctk.BooleanVar(value=True)
        self._rh = ctk.BooleanVar(value=True)
        rr = ctk.CTkFrame(page, fg_color="transparent")
        rr.pack(anchor="w", padx=32, pady=4)
        for v, l in [(self._rj, "JSON"), (self._rc, "CSV"), (self._rh, "HTML")]:
            ctk.CTkCheckBox(rr, text=l, variable=v).pack(side="left", padx=10)

        # Dry-run
        sep(page)
        self._dry = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            page,
            text="🏜️  Dry-run — preview all actions, zero files modified",
            variable=self._dry,
            fg_color=ORANGE,
            hover_color="#cc7700",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=24, pady=8)

        # Action buttons
        br = ctk.CTkFrame(page, fg_color="transparent")
        br.pack(anchor="w", padx=24, pady=(8, 24))
        ctk.CTkButton(
            br,
            text="▶️  Start Job",
            width=160,
            height=40,
            fg_color=GREEN,
            text_color="#000",
            hover_color="#00cc66",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._start,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            br, text="💾 Save Config", width=130, command=self._save_cfg
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            br,
            text="📂 Load Config",
            width=130,
            fg_color="#2a2a2a",
            command=self._load_cfg,
        ).pack(side="left", padx=4)
        return page

    def _path_row(self, parent, label, var, cmd):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(anchor="w", padx=24, pady=3, fill="x")
        ctk.CTkLabel(r, text=label, width=110, anchor="w", text_color="#aaa").pack(
            side="left"
        )
        ctk.CTkEntry(r, textvariable=var, width=400).pack(side="left", padx=6)
        ctk.CTkButton(r, text="Browse", width=80, command=cmd).pack(side="left")

    def _pick(self, var):
        d = filedialog.askdirectory()
        if d:
            var.set(d)

    # ─────────────────────────────────────────────────────────────────────────
    # PAGE: RUN
    # ─────────────────────────────────────────────────────────────────────────
    def _pg_run(self):
        page = ctk.CTkFrame(self._content, fg_color=BG)
        ctk.CTkLabel(
            page,
            text="▶️  Job Progress",
            font=ctk.CTkFont(size=21, weight="bold"),
            text_color=ACCENT,
        ).pack(anchor="w", padx=24, pady=(22, 8))

        cf = ctk.CTkFrame(page, fg_color="transparent")
        cf.pack(fill="x", padx=24, pady=4)
        self._cs = StatCard(cf, "Scanned", color=ACCENT)
        self._cr = StatCard(cf, "Renamed", color=YELLOW)
        self._cu = StatCard(cf, "Unique Moved", color=GREEN)
        self._cd = StatCard(cf, "Shredded", color=RED)
        self._ce = StatCard(cf, "Elapsed (s)", color=ORANGE)
        for c in [self._cs, self._cr, self._cu, self._cd, self._ce]:
            c.pack(side="left", padx=5, expand=True, fill="x")

        self._prog_lbl = ctk.CTkLabel(page, text="Idle", text_color="#666")
        self._prog_lbl.pack(anchor="w", padx=24, pady=(12, 2))
        self._prog = ctk.CTkProgressBar(page, height=10, progress_color=ACCENT)
        self._prog.pack(fill="x", padx=24, pady=(0, 8))
        self._prog.set(0)

        ctk.CTkLabel(
            page,
            text="Live Output",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#555",
        ).pack(anchor="w", padx=24, pady=(6, 2))
        self._run_box = ctk.CTkTextbox(
            page,
            fg_color="#0a0a0a",
            text_color="#ccc",
            font=ctk.CTkFont(family="Courier New", size=11),
            height=340,
        )
        self._run_box.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        self._run_box.configure(state="disabled")

        br = ctk.CTkFrame(page, fg_color="transparent")
        br.pack(anchor="w", padx=24, pady=(0, 16))
        self._stop_btn = ctk.CTkButton(
            br,
            text="⏹ Stop",
            fg_color=RED,
            hover_color="#aa0000",
            width=110,
            state="disabled",
            command=self._stop,
        )
        self._stop_btn.pack(side="left", padx=4)
        ctk.CTkButton(
            br,
            text="🗑 Clear",
            width=90,
            fg_color="#2a2a2a",
            command=lambda: self._clear_box(self._run_box),
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            br, text="📊 Open Report", width=130, command=self._open_html
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            br, text="📂 Open Target", width=130, command=self._open_target
        ).pack(side="left", padx=4)
        return page

    # ─────────────────────────────────────────────────────────────────────────
    # PAGE: LOG
    # ─────────────────────────────────────────────────────────────────────────
    def _pg_log(self):
        page = ctk.CTkFrame(self._content, fg_color=BG)
        h = ctk.CTkFrame(page, fg_color="transparent")
        h.pack(fill="x", padx=24, pady=(22, 8))
        ctk.CTkLabel(
            h,
            text="📋  Full Log",
            font=ctk.CTkFont(size=21, weight="bold"),
            text_color=ACCENT,
        ).pack(side="left")
        ctk.CTkButton(h, text="💾 Save", width=90, command=self._save_log).pack(
            side="right", padx=4
        )
        ctk.CTkButton(
            h,
            text="🗑 Clear",
            width=90,
            fg_color="#2a2a2a",
            command=lambda: self._clear_box(self._log_box),
        ).pack(side="right", padx=4)
        self._log_box = ctk.CTkTextbox(
            page,
            fg_color="#0a0a0a",
            text_color="#ccc",
            font=ctk.CTkFont(family="Courier New", size=11),
        )
        self._log_box.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        self._log_box.configure(state="disabled")
        return page

    # ─────────────────────────────────────────────────────────────────────────
    # PAGE: REPORTS
    # ─────────────────────────────────────────────────────────────────────────
    def _pg_reports(self):
        page = ctk.CTkFrame(self._content, fg_color=BG)
        ctk.CTkLabel(
            page,
            text="📊  Reports",
            font=ctk.CTkFont(size=21, weight="bold"),
            text_color=ACCENT,
        ).pack(anchor="w", padx=24, pady=(22, 12))
        for txt, clr, cmd in [
            ("🌐  Open HTML Report", ACCENT, self._open_html),
            ("📋  Open CSV Report", "#1a3a1a", self._open_csv),
            ("📄  Open JSON Report", "#1a1a3a", self._open_json),
            ("📂  Open Target Folder", "#3a2a1a", self._open_target),
            ("📂  Open Source Folder", "#2a1a1a", self._open_source),
        ]:
            ctk.CTkButton(
                page, text=txt, width=300, height=38, fg_color=clr, command=cmd
            ).pack(anchor="w", padx=24, pady=3)

        ctk.CTkLabel(
            page,
            text="Last run summary",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#555",
        ).pack(anchor="w", padx=24, pady=(22, 4))
        self._summary = ctk.CTkTextbox(
            page,
            fg_color="#0a0a0a",
            text_color="#ccc",
            font=ctk.CTkFont(family="Courier New", size=11),
            height=280,
        )
        self._summary.pack(fill="x", padx=24, pady=(0, 16))
        self._summary.configure(state="disabled")
        return page

    # ─────────────────────────────────────────────────────────────────────────
    # PAGE: UNDO
    # ─────────────────────────────────────────────────────────────────────────
    def _pg_undo(self):
        page = ctk.CTkFrame(self._content, fg_color=BG)
        ctk.CTkLabel(
            page,
            text="↩️  Undo Last Job",
            font=ctk.CTkFont(size=21, weight="bold"),
            text_color=ACCENT,
        ).pack(anchor="w", padx=24, pady=(22, 4))
        ctk.CTkLabel(
            page,
            text="Reads filevault_report.json and moves files back to their original locations.",
            text_color="#888",
        ).pack(anchor="w", padx=24, pady=(0, 16))

        rp = ctk.CTkFrame(page, fg_color="transparent")
        rp.pack(anchor="w", padx=24, pady=4)
        self._undo_report = ctk.StringVar(value="filevault_report.json")
        ctk.CTkLabel(rp, text="Report file:").pack(side="left")
        ctk.CTkEntry(rp, textvariable=self._undo_report, width=360).pack(
            side="left", padx=8
        )
        ctk.CTkButton(
            rp,
            text="Browse",
            width=80,
            command=lambda: self._undo_report.set(
                filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
                or self._undo_report.get()
            ),
        ).pack(side="left")

        self._undo_dry = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            page,
            text="Dry-run (preview undo without moving files)",
            variable=self._undo_dry,
        ).pack(anchor="w", padx=24, pady=8)

        br = ctk.CTkFrame(page, fg_color="transparent")
        br.pack(anchor="w", padx=24, pady=8)
        ctk.CTkButton(
            br,
            text="↩️  Undo Last Job",
            width=180,
            height=40,
            fg_color=ORANGE,
            text_color="#000",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._do_undo,
        ).pack(side="left", padx=4)

        self._undo_log = ctk.CTkTextbox(
            page,
            fg_color="#0a0a0a",
            text_color="#ccc",
            font=ctk.CTkFont(family="Courier New", size=11),
            height=300,
        )
        self._undo_log.pack(fill="both", expand=True, padx=24, pady=(8, 16))
        self._undo_log.configure(state="disabled")
        return page

    # ─────────────────────────────────────────────────────────────────────────
    # PAGE: SETTINGS
    # ─────────────────────────────────────────────────────────────────────────
    def _pg_settings(self):
        page = ctk.CTkScrollableFrame(self._content, fg_color=BG)
        ctk.CTkLabel(
            page,
            text="🛠️  Settings",
            font=ctk.CTkFont(size=21, weight="bold"),
            text_color=ACCENT,
        ).pack(anchor="w", padx=24, pady=(22, 12))

        section(page, "🎨  Appearance")
        self._theme = ctk.StringVar(value="dark")
        tr = ctk.CTkFrame(page, fg_color="transparent")
        tr.pack(anchor="w", padx=32, pady=4)
        for v, l in [("dark", "Dark"), ("light", "Light"), ("system", "System")]:
            ctk.CTkRadioButton(
                tr,
                text=l,
                variable=self._theme,
                value=v,
                command=lambda vv=v: ctk.set_appearance_mode(vv),
            ).pack(side="left", padx=8)

        section(page, "📝  Log File")
        lr = ctk.CTkFrame(page, fg_color="transparent")
        lr.pack(anchor="w", padx=32, pady=4)
        self._logfile = ctk.StringVar(value="filevault.log")
        ctk.CTkEntry(lr, textvariable=self._logfile, width=340).pack(side="left")
        ctk.CTkButton(
            lr,
            text="Browse",
            width=80,
            command=lambda: self._logfile.set(
                filedialog.asksaveasfilename(defaultextension=".log")
                or self._logfile.get()
            ),
        ).pack(side="left", padx=8)

        section(page, "🔔  Post-Job")
        self._auto_open = ctk.BooleanVar(value=True)
        self._notify = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            page,
            text="Auto-open HTML report when job finishes",
            variable=self._auto_open,
        ).pack(anchor="w", padx=32, pady=2)
        ctk.CTkCheckBox(
            page,
            text="Show popup notification when job finishes",
            variable=self._notify,
        ).pack(anchor="w", padx=32, pady=2)

        section(page, "🪟  Windows Context Menu (run as Administrator)")
        br = ctk.CTkFrame(page, fg_color="transparent")
        br.pack(anchor="w", padx=32, pady=4)
        ctk.CTkButton(
            br,
            text="Register",
            width=120,
            command=lambda: fv.register_context_menu(__file__),
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            br,
            text="Unregister",
            width=120,
            fg_color="#2a2a2a",
            command=fv.unregister_context_menu,
        ).pack(side="left", padx=4)
        return page

    # ─────────────────────────────────────────────────────────────────────────
    # PAGE: ABOUT
    # ─────────────────────────────────────────────────────────────────────────
    def _pg_about(self):
        page = ctk.CTkFrame(self._content, fg_color=BG)
        ctk.CTkLabel(
            page,
            text="🗄️ FileVault v4.0",
            font=ctk.CTkFont(size=34, weight="bold"),
            text_color=ACCENT,
        ).pack(pady=(48, 4))
        ctk.CTkLabel(
            page,
            text="Intelligent File Organizer, Deduplicator & Secure Shredder",
            font=ctk.CTkFont(size=13),
            text_color="#666",
        ).pack(pady=4)
        feats = [
            "🧬 Exact dedup — BLAKE3/SHA-256 bit-perfect",
            "📸 Photo dedup — pHash 256-bit perceptual hash",
            "✅ Copy integrity gate — verify before shred",
            "📄 PDF/eBook smart rename — 3-library fallback",
            "📝 Office doc smart rename — DOCX/XLSX/PPTX",
            "🔬 EXIF editor — strip GPS, device, date",
            "🔒 DoD 5220.22-M secure shred (up to 35 passes)",
            "👁️ Watch mode — real-time background daemon",
            "⏰ Scheduler — once / daily / interval",
            "↩️ Undo — reverse last job from report",
            "🔌 Plugin system — custom rename rules",
            "🪟 Windows context menu integration",
        ]
        ff = ctk.CTkFrame(page, fg_color=CARD, corner_radius=12)
        ff.pack(padx=60, pady=16, fill="x")
        for f in feats:
            ctk.CTkLabel(ff, text=f, text_color="#ccc", font=ctk.CTkFont(size=11)).pack(
                anchor="w", padx=24, pady=2
            )
        ctk.CTkButton(
            page,
            text="⭐ Star on GitHub",
            width=200,
            fg_color=ACCENT,
            text_color="#000",
            command=lambda: webbrowser.open("https://github.com"),
        ).pack(pady=12)
        return page

    # ─────────────────────────────────────────────────────────────────────────
    # BUILD CFG  ← exact same dict structure run_job() and YAML expects
    # ─────────────────────────────────────────────────────────────────────────
    def _build_cfg(self) -> dict:
        excl = [x.strip() for x in self._excl.get().split(",") if x.strip()]
        exif = {}
        if self._exif_rm_gps.get():
            exif["remove_gps"] = True
        if self._exif_rm_device.get():
            exif["remove_device"] = True
        if self._exif_rm_date.get():
            exif["set_datetime"] = None
        if self._exif_set_author.get():
            exif["set_author"] = self._exif_set_author.get()
        if self._exif_set_desc.get():
            exif["set_description"] = self._exif_set_desc.get()

        return {
            "source": self._src_var.get(),
            "target": self._tgt_var.get(),
            "dry_run": self._dry.get(),
            "passes": self._passes.get(),
            "workers": self._workers.get(),
            "exclude": excl,
            "move_mode": self._move_mode.get(),
            "use_subfolders": self._use_sf.get(),
            "subfolder_mode": self._sf_mode.get(),
            "metadata_rename": self._r_meta.get(),
            "rename_folder": self._r_folder.get(),
            "rename_date_prefix": self._r_date.get(),
            "shred_dupes": self._shrd_dupes.get(),
            "shred_all": self._shrd_all.get(),
            "quick_scan": self._quick.get(),
            "exif_edits": exif,
            "plugin_dir": self._plugin_dir.get(),
            "report_json": self._rj.get(),
            "report_csv": self._rc.get(),
            "report_html": self._rh.get(),
            "log_file": (
                self._logfile.get() if hasattr(self, "_logfile") else "filevault.log"
            ),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # START / STOP
    # ─────────────────────────────────────────────────────────────────────────
    def _start(self):
        cfg = self._build_cfg()
        if not cfg["source"] or not cfg["target"]:
            messagebox.showerror("Missing Paths", "Set both Source and Target.")
            return

        fv.setup_logging(cfg.get("log_file", "filevault.log"))
        self._running = True
        self._stop_btn.configure(state="normal")
        self._prog.set(0.02)
        self._prog_lbl.configure(text="Running...")
        self._reset_cards()
        self._clear_box(self._run_box)
        self._show("run", self._pg_run)  # switch to run page

        def _thread():
            try:
                report = fv.run_job(cfg)
                self._report = report
                self.after(0, lambda: self._on_done(report))
            except Exception as e:
                self.after(0, lambda: self._on_error(str(e)))
            finally:
                self._running = False
                self.after(0, lambda: self._stop_btn.configure(state="disabled"))

        threading.Thread(target=_thread, daemon=True).start()

    def _stop(self):
        self._running = False
        self._append_log("[GUI] Stop requested.")

    def _on_done(self, r: dict):
        self._prog.set(1.0)
        self._prog_lbl.configure(text="✅  Complete")
        self._cs.set(r.get("total_files", "—"))
        self._cr.set(r.get("renamed_count", "—"))
        self._cu.set(r.get("unique_moved", "—"))
        self._cd.set(r.get("dupes_shredded", "—"))
        self._ce.set(r.get("elapsed", "—"))
        # Update summary
        self._summary.configure(state="normal")
        self._summary.delete("1.0", "end")
        self._summary.insert("end", json.dumps(r, indent=2, default=str))
        self._summary.configure(state="disabled")
        if hasattr(self, "_auto_open") and self._auto_open.get():
            self._open_html()
        if hasattr(self, "_notify") and self._notify.get():
            messagebox.showinfo("FileVault", "✅ Job complete! Check Reports tab.")

    def _on_error(self, e: str):
        self._prog_lbl.configure(text=f"❌ Error")
        messagebox.showerror("FileVault Error", e)

    # ─────────────────────────────────────────────────────────────────────────
    # UNDO
    # ─────────────────────────────────────────────────────────────────────────
    def _do_undo(self):
        rp = self._undo_report.get()
        dry = self._undo_dry.get()

        old_handlers = fv.log.handlers[:]
        undo_lines = []

        class UH(logging.Handler):
            def emit(self_, rec):
                undo_lines.append(self_.format(rec))

        uh = UH()
        uh.setFormatter(logging.Formatter("%(message)s"))
        fv.log.addHandler(uh)
        fv.undo_last_job(rp, dry_run=dry)
        fv.log.removeHandler(uh)

        self._undo_log.configure(state="normal")
        self._undo_log.delete("1.0", "end")
        self._undo_log.insert("end", "".join(undo_lines))
        self._undo_log.configure(state="disabled")

    # ─────────────────────────────────────────────────────────────────────────
    # CONFIG SAVE / LOAD
    # ─────────────────────────────────────────────────────────────────────────
    def _save_cfg(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".yaml", filetypes=[("YAML", "*.yaml"), ("JSON", "*.json")]
        )
        if not path:
            return
        cfg = self._build_cfg()
        try:
            import yaml

            Path(path).write_text(
                yaml.dump(cfg, default_flow_style=False), encoding="utf-8"
            )
        except ImportError:
            Path(path).write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        messagebox.showinfo("Saved", f"Config saved: {path}")

    def _load_cfg(self):
        path = filedialog.askopenfilename(
            filetypes=[("Config", "*.yaml *.json"), ("All", "*.*")]
        )
        if not path:
            return
        try:
            if path.endswith(".yaml"):
                import yaml

                with open(path) as f:
                    cfg = yaml.safe_load(f) or {}
            else:
                with open(path) as f:
                    cfg = json.load(f)
            self._src_var.set(cfg.get("source", ""))
            self._tgt_var.set(cfg.get("target", ""))
            self._dry.set(cfg.get("dry_run", False))
            self._passes.set(cfg.get("passes", 7))
            self._workers.set(cfg.get("workers", 8))
            self._move_mode.set(cfg.get("move_mode", "all"))
            self._use_sf.set(cfg.get("use_subfolders", True))
            self._sf_mode.set(cfg.get("subfolder_mode", "unique_dupes"))
            self._r_meta.set(cfg.get("metadata_rename", True))
            self._r_folder.set(cfg.get("rename_folder", True))
            self._r_date.set(cfg.get("rename_date_prefix", False))
            self._shrd_dupes.set(cfg.get("shred_dupes", True))
            self._shrd_all.set(cfg.get("shred_all", False))
            self._quick.set(cfg.get("quick_scan", False))
            self._excl.set(", ".join(cfg.get("exclude", [])))
            messagebox.showinfo("Loaded", f"Config loaded: {path}")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────
    def _append_log(self, msg: str):
        self._log_lines.append(msg)

        def _w():
            for box in [
                b
                for b in [
                    getattr(self, "_run_box", None),
                    getattr(self, "_log_box", None),
                ]
                if b
            ]:
                box.configure(state="normal")
                box.insert("end", msg + "")
                box.see("end")
                box.configure(state="disabled")

        self.after(0, _w)

    def _clear_box(self, box):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.configure(state="disabled")

    def _reset_cards(self):
        for c in [self._cs, self._cr, self._cu, self._cd, self._ce]:
            c.set("—")

    def _open_html(self):
        p = Path("filevault_report.html")
        if p.exists():
            webbrowser.open(p.resolve().as_uri())
        else:
            messagebox.showwarning("Not found", "Run a job first.")

    def _open_csv(self):
        p = Path("filevault_moves.csv")
        if p.exists():
            webbrowser.open(p.resolve().as_uri())
        else:
            messagebox.showwarning("Not found", "Run a job first.")

    def _open_json(self):
        p = Path("filevault_report.json")
        if p.exists():
            webbrowser.open(p.resolve().as_uri())
        else:
            messagebox.showwarning("Not found", "Run a job first.")

    def _open_target(self):
        t = self._tgt_var.get()
        if t and Path(t).exists():
            webbrowser.open(Path(t).resolve().as_uri())
        else:
            messagebox.showwarning("Not set", "Set target folder first.")

    def _open_source(self):
        s = self._src_var.get()
        if s and Path(s).exists():
            webbrowser.open(Path(s).resolve().as_uri())

    def _save_log(self):
        p = filedialog.asksaveasfilename(defaultextension=".log")
        if p:
            Path(p).write_text("".join(self._log_lines), encoding="utf-8")


def main(source_arg: str = ""):
    app = App(source_arg=source_arg)
    app.mainloop()


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    main(source_arg=src)
