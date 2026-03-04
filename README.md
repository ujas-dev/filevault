# 🗄️ FileVault v4.0

> Complete file organizer, deduplicator & secure shredder.
> **One engine — CLI, YAML config, GUI all call the exact same `run_job()` function.**

[![Version](https://img.shields.io/badge/version-4.0.0-blue)]()
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)]()
[![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-purple)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()

---

## Architecture

```
filevault.py          ← THE ENGINE (all logic lives here)
  └── run_job(cfg)    ← single function: CLI, GUI and YAML all call this

filevault_gui.py      ← GUI frontend: builds same cfg dict, calls run_job()
filevault.yaml        ← YAML config: loaded to same cfg dict, runs same engine
plugins/              ← custom rename rule plugins
```

**There is no gap between GUI and CLI.** If a feature works in the GUI, it works from CLI and YAML too.

---

## Quick Start

```bash
pip install customtkinter blake3 pymupdf pypdf pikepdf
pip install python-docx openpyxl python-pptx Pillow imagehash
pip install watchdog pyyaml piexif

# CLI — basic
python filevault.py /source /target

# CLI — dry-run, move unique only, no sub-folders
python filevault.py /source /target --dry-run --move-mode unique --no-subfolders

# YAML config
python filevault.py --config filevault.yaml

# GUI (requires display — see VNC setup for Docker)
python filevault_gui.py

# Or launch GUI from CLI
python filevault.py --gui

# Watch mode (real-time daemon)
python filevault.py /source /target --watch

# Scheduler — daily at 2 AM
python filevault.py /source /target --schedule daily --at 02:00

# Undo last job
python filevault.py --undo

# Windows right-click menu (run as Administrator)
python filevault.py --register-context-menu
```

---

## CLI Reference

| Flag | Default | Description |
|---|---|---|
| `source` `target` | required | Source and target folders |
| `--config FILE` | — | Load YAML/JSON config (CLI flags override it) |
| `--dry-run` | off | Preview all actions, zero files touched |
| `--move-mode` | `all` | `all` / `unique` / `dupes` |
| `--no-subfolders` | off | Dump all files flat in target root |
| `--subfolder-mode` | `unique_dupes` | `unique_dupes` / `by_type` / `flat` |
| `--passes N` | 7 | Shred overwrite passes |
| `--workers N` | 8 | Parallel hash threads |
| `--no-shred-dupes` | off | Move dupes without shredding source |
| `--shred-all` | off | Shred even unique files after copy |
| `--date-prefix` | off | Prefix images with EXIF date |
| `--no-metadata-rename` | off | Skip smart rename |
| `--quick-scan` | off | Hash first 4MB only (faster) |
| `--plugin-dir DIR` | — | Load rename plugins from folder |
| `--watch` | off | Real-time file watcher daemon |
| `--schedule` | — | `once` / `daily` / `interval` |
| `--at TIME` | — | Time for `once`/`daily` e.g. `02:00` |
| `--every N` | 60 | Minutes for `interval` |
| `--undo` | off | Reverse last job from report |
| `--no-json/csv/html` | off | Suppress specific report formats |
| `--register-context-menu` | — | Add Windows right-click menu entry |
| `--gui` | off | Launch GUI |

---

## Move Modes

| Mode | What happens | Use case |
|---|---|---|
| `all` | Move unique + dupes, source fully emptied | Full migration |
| `unique` | Move only unique files, shred dupes in-place, nothing goes to target/duplicates | Clean archive |
| `dupes` | Move only extra copies to target, unique files stay | Audit duplicates |

---

## Output Folder Structure

| Subfolder Mode | Result |
|---|---|
| `unique_dupes` | `target/unique/` + `target/duplicates/` |
| `by_type` | `target/pdf/`, `target/images/`, `target/office/`, `target/other/` |
| `flat` | All files directly in `target/`, no sub-folders created |

Set `use_subfolders: false` in YAML or `--no-subfolders` in CLI to skip sub-folder creation entirely.

---

## EXIF Metadata Editor

Applies to image files before copy. Configure in YAML:

```yaml
exif_edits:
  remove_gps: true              # strip GPS coordinates (privacy)
  remove_device: true           # strip Make/Model/Software
  set_datetime: null            # null = remove all date fields
  set_author: "Your Name"       # set Artist + Copyright
  set_description: null         # null = remove description
```

Or in GUI: ⚙️ Configure → 🔬 EXIF Metadata Editor section.

---

## Plugin System

Drop `.py` files in a folder and point `plugin_dir` at it:

```python
# plugins/my_rule.py
EXTENSIONS = [".pdf", ".epub"]   # or ["*"] for all

def rename(fp, meta) -> str | None:
    if meta.get("title"):
        return f"[DONE] {meta['title']}{fp.suffix}"
    return None          # None = skip this plugin
```

---

## Scheduler (YAML)

```yaml
# One-time
schedule:
  type: once
  at: "2026-03-10 02:00"

# Daily
schedule:
  type: daily
  at: "02:00"

# Every N minutes
schedule:
  type: interval
  every_minutes: 60
```

---

## Undo

Every job writes `filevault_report.json`. Undo reads it and reverse-moves everything:

```bash
python filevault.py --undo                          # real undo
python filevault.py --undo --dry-run                # preview undo
python filevault.py --undo --config filevault.yaml  # custom report path
```

GUI: ↩️ Undo tab.

---

## What Makes FileVault Unique

| Feature | FileVault | CCleaner | dupeGuru | AllDup |
|---|---|---|---|---|
| Copy integrity gate (verify before shred) | ✅ | ❌ | ❌ | ❌ |
| PDF/eBook smart rename from metadata | ✅ | ❌ | ❌ | ❌ |
| EXIF metadata editor (strip GPS, date, device) | ✅ | ❌ | ❌ | ❌ |
| Plugin system for rename rules | ✅ | ❌ | ❌ | ❌ |
| Watch mode daemon | ✅ | ❌ | ❌ | ❌ |
| Undo last job | ✅ | ❌ | ❌ | ❌ |
| Scheduler (once/daily/interval) | ✅ | ❌ | ❌ | ❌ |
| Windows context-menu integration | ✅ | ✅ | ❌ | ❌ |
| CLI + YAML + GUI same engine | ✅ | ❌ | ❌ | ❌ |
| HTML audit dashboard (offline, shareable) | ✅ | ❌ | ❌ | ❌ |
| Photo perceptual hash (survives recompress) | ✅ | ❌ | ✅ | ✅ |
| DoD secure shred (up to 35 passes) | ✅ | ❌ | ❌ | ❌ |
| Fully open source | ✅ | ❌ | ✅ | ❌ |

---

## Install (all features)

```bash
pip install customtkinter blake3 pymupdf pypdf pikepdf python-docx openpyxl python-pptx
pip install Pillow imagehash watchdog pyyaml piexif
```

Minimum (no GUI, no smart rename, no perceptual hash):

```bash
# Zero extra deps — uses stdlib sha256, basic file ops
python filevault.py /source /target
```

---

## License

MIT
