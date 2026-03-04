# 🤝 Contributing to FileVault

Thank you for taking the time to contribute! FileVault is a community-driven open-source tool and every contribution matters — from bug fixes and new features to documentation improvements and new plugins.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Report a Bug](#how-to-report-a-bug)
- [How to Request a Feature](#how-to-request-a-feature)
- [How to Submit a Plugin](#how-to-submit-a-plugin)
- [Development Setup](#development-setup)
- [Architecture — Read This First](#architecture--read-this-first)
- [Making a Pull Request](#making-a-pull-request)
- [Coding Standards](#coding-standards)

---

## Code of Conduct

Be respectful. Be constructive. We follow the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

---

## How to Report a Bug

1. Search [existing issues](../../issues) first — it may already be reported.
2. Click **New Issue → 🐛 Bug Report**.
3. Fill in the template completely — especially:
   - Your OS, Python version, and installed packages
   - The exact CLI command or YAML config you used
   - The full log output from `filevault.log`

---

## How to Request a Feature

1. Click **New Issue → 🚀 Feature Request**.
2. Explain the problem you're solving, not just the solution you want.
3. Note which interface it affects (CLI / GUI / YAML / plugin).

---

## How to Submit a Plugin

Rename plugins are `.py` files dropped in the `plugins/` directory.

1. Fork the repo and add your plugin to `plugins/community/your_plugin.py`.
2. Follow the plugin template in `plugins/example_pdf_rename.py`.
3. Open a PR with the **🔌 Plugin Submission** template.

---

## Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/filevault.git
cd filevault

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Run a quick smoke test (dry-run, won't touch files)
python filevault.py /tmp/test_source /tmp/test_target --dry-run
```

---

## Architecture — Read This First

```
filevault.py
  └── run_job(cfg: dict) → dict    ← SINGLE engine function
        ├── traverse()
        ├── build_dup_sets()       ← exact hash + pHash
        ├── folder_name_rename()
        ├── apply_plugins()
        ├── get_metadata() + build_smart_name()
        ├── apply_exif_edits()
        ├── safe_move()            ← copy integrity gate + shred
        └── save_reports()

filevault_gui.py
  └── App._build_cfg() → dict      ← builds SAME dict as YAML config
  └── threading.Thread → fv.run_job(cfg)
```

**The golden rule: CLI, GUI, and YAML all call `run_job(cfg)` with the same dict. Never add logic to the GUI that isn't in the engine.**

---

## Making a Pull Request

1. Fork the repo → create a branch: `git checkout -b fix/my-bugfix`
2. Make your change.
3. Test via CLI, GUI, and with a YAML config.
4. Commit with a clear message:
   ```
   fix: handle PermissionError during shred on Windows
   feat: add FLAC audio smart rename plugin
   docs: update YAML config example for scheduler
   ```
5. Open a PR and fill in the PR template.

**PR Rules:**
- Never change the `run_job(cfg)` signature without updating CLI arg parser AND GUI `_build_cfg()`.
- Every new config key must have: CLI flag + YAML example + GUI widget + README table entry.
- Dry-run mode must always produce zero file modifications.

---

## Coding Standards

- Python 3.10+ syntax.
- No external dependencies required for the core engine — all imports are optional with `try/except ImportError`.
- Log everything via `log.info()` / `log.warning()` / `log.error()` — never `print()` in the engine.
- All file operations go through `safe_move()` — never use `shutil.move()` directly.
- Format with `black`, lint with `ruff`.

---

## Questions?

Open a [Discussion](../../discussions) — not an issue — for questions, ideas, or general chat.
