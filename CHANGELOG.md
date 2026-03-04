# Changelog

All notable changes to FileVault will be documented here.
Format: [Semantic Versioning](https://semver.org/)

---

# Changelog

## [4.0.0] — 2026-03-04  ← current
### Added
- Single engine: run_job(cfg) — CLI, GUI, YAML all identical
- Copy integrity gate
- EXIF metadata editor
- Plugin system
- Undo last job
- Scheduler (once/daily/interval)
- Windows context-menu integration
- Move mode (all/unique/dupes)
- Subfolder mode (unique_dupes/by_type/flat)
- EXIF date prefix for images
### Fixed
- GUI was not calling engine (complete rewrite)
- Shred was not running
- Reports were not being written

---

## [3.0.0] — 2026-03-04
### Added
- CustomTkinter dark-themed GUI frontend
- Move mode UI
- Subfolder control UI
### Known Issues
- GUI did not actually call the engine (fixed in v4.0.0)

---

## [2.0.0] — 2026-03-04
### Added
- PDF/eBook/Office smart rename (3-library fallback chain)
- pHash perceptual image deduplication
- DoD secure shred (multi-pass)
- Watch mode daemon
- JSON + CSV + HTML audit reports
- YAML config support

---

## [1.0.0] — 2026-03-04
### Added
- Initial release
- Recursive file traversal
- Exact dedup via BLAKE3/SHA-256
- Copy + delete with size filter
