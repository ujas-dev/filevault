#!/usr/bin/env python3
"""
FileVault v4.0 — Complete rewrite
Single source of truth: CLI + YAML + GUI all call run_job(cfg) identically.
"""

import argparse
import csv
import datetime
import fnmatch
import hashlib
import importlib.util
import json
import logging
import os
import platform
import re
import sched
import shutil
import subprocess
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING — module-level logger, GUI can attach its own handler
# ─────────────────────────────────────────────────────────────────────────────
log = logging.getLogger("filevault")
log.setLevel(logging.DEBUG)


def setup_logging(log_file: str = "filevault.log", level=logging.INFO):
    log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(level)
    sh.setFormatter(fmt)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    log.addHandler(sh)
    log.addHandler(fh)


# ─────────────────────────────────────────────────────────────────────────────
# HASH ENGINE
# ─────────────────────────────────────────────────────────────────────────────
try:
    import blake3 as _blake3

    HASH_ENGINE = "blake3"

    def _compute_hash(fp: Path, limit: int = 0) -> str:
        h = _blake3.blake3()
        read = 0
        with open(fp, "rb") as f:
            while buf := f.read(1 << 20):
                h.update(buf)
                read += len(buf)
                if limit and read >= limit:
                    break
        return h.hexdigest()

except ImportError:
    HASH_ENGINE = "sha256"

    def _compute_hash(fp: Path, limit: int = 0) -> str:
        h = hashlib.sha256()
        read = 0
        with open(fp, "rb") as f:
            while buf := f.read(1 << 20):
                h.update(buf)
                read += len(buf)
                if limit and read >= limit:
                    break
        return h.hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# FILE CATEGORIES
# ─────────────────────────────────────────────────────────────────────────────
PDF_EXTS = {".pdf"}
EBOOK_EXTS = {".epub", ".mobi", ".azw", ".azw3", ".fb2", ".djvu", ".lit"}
OFFICE_EXTS = {
    ".docx",
    ".doc",
    ".odt",
    ".rtf",
    ".xlsx",
    ".xls",
    ".ods",
    ".pptx",
    ".ppt",
    ".odp",
    ".pages",
    ".numbers",
    ".key",
    ".txt",
    ".md",
    ".rst",
}
IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
    ".heic",
    ".heif",
    ".avif",
    ".raw",
    ".cr2",
    ".nef",
    ".arw",
    ".dng",
}


def file_category(fp: Path) -> str:
    e = fp.suffix.lower()
    if e in PDF_EXTS:
        return "pdf"
    if e in EBOOK_EXTS:
        return "ebook"
    if e in OFFICE_EXTS:
        return "office"
    if e in IMAGE_EXTS:
        return "image"
    return "other"


# ─────────────────────────────────────────────────────────────────────────────
# SANITIZE
# ─────────────────────────────────────────────────────────────────────────────
_ILLEGAL = re.compile(r'[\/:*?"<>|-]')


def sanitize(s: str, maxlen: int = 160) -> str:
    return (_ILLEGAL.sub("_", s).strip(". ") or "unnamed")[:maxlen]


# ─────────────────────────────────────────────────────────────────────────────
# METADATA EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────
def _pdf_meta(fp: Path) -> dict:
    m = {"title": "", "author": ""}
    for lib in ("fitz", "pypdf", "pikepdf"):
        try:
            if lib == "fitz":
                import fitz

                doc = fitz.open(str(fp))
                raw = doc.metadata or {}
                m["title"] = (raw.get("title") or "").strip()
                m["author"] = (raw.get("author") or "").strip()
                if not m["title"] and doc.page_count:
                    cands = [
                        (sp["size"], sp["text"].strip())
                        for b in doc[0].get_text("dict").get("blocks", [])
                        for ln in b.get("lines", [])
                        for sp in ln.get("spans", [])
                        if sp.get("text", "").strip() and sp.get("size", 0) > 14
                    ]
                    if cands:
                        m["title"] = max(cands)[1]
                doc.close()
            elif lib == "pypdf":
                from pypdf import PdfReader

                info = PdfReader(str(fp)).metadata or {}
                m["title"] = (info.get("/Title") or "").strip()
                m["author"] = (info.get("/Author") or "").strip()
            elif lib == "pikepdf":
                import pikepdf

                with pikepdf.open(str(fp)) as pdf:
                    di = pdf.docinfo
                    m["title"] = str(di.get("/Title", "")).strip()
                    m["author"] = str(di.get("/Author", "")).strip()
            if m["title"] or m["author"]:
                return m
        except Exception:
            continue
    return m


def _epub_meta(fp: Path) -> dict:
    m = {"title": "", "author": ""}
    try:
        import xml.etree.ElementTree as ET
        import zipfile

        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        with zipfile.ZipFile(str(fp)) as zf:
            container = ET.fromstring(zf.read("META-INF/container.xml"))
            opf_path = container.find(
                ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
            ).get("full-path")
            opf = ET.fromstring(zf.read(opf_path))
            t = opf.find(".//dc:title", ns)
            a = opf.find(".//dc:creator", ns)
            m["title"] = (t.text or "").strip() if t is not None else ""
            m["author"] = (a.text or "").strip() if a is not None else ""
    except Exception:
        pass
    return m


def _office_meta(fp: Path) -> dict:
    m = {"title": "", "author": ""}
    ext = fp.suffix.lower()
    try:
        if ext in {".docx", ".doc"}:
            import docx

            d = docx.Document(str(fp))
            p = d.core_properties
            m["title"] = (p.title or "").strip()
            m["author"] = (p.author or "").strip()
        elif ext in {".xlsx", ".xls"}:
            import openpyxl

            wb = openpyxl.load_workbook(str(fp), read_only=True, data_only=True)
            p = wb.properties
            m["title"] = (p.title or "").strip()
            m["author"] = (p.creator or "").strip()
            wb.close()
        elif ext in {".pptx", ".ppt"}:
            from pptx import Presentation

            prs = Presentation(str(fp))
            p = prs.core_properties
            m["title"] = (p.title or "").strip()
            m["author"] = (p.author or "").strip()
        elif ext in {".odt", ".ods", ".odp"}:
            import xml.etree.ElementTree as ET
            import zipfile

            ns = {
                "dc": "http://purl.org/dc/elements/1.1/",
                "meta": "http://openoffice.org/2004/meta",
            }
            with zipfile.ZipFile(str(fp)) as zf:
                tree = ET.fromstring(zf.read("meta.xml"))
                t = tree.find(".//dc:title", ns)
                a = tree.find(".//meta:initial-creator", ns)
                m["title"] = (t.text or "").strip() if t is not None else ""
                m["author"] = (a.text or "").strip() if a is not None else ""
    except Exception:
        pass
    return m


def _image_exif(fp: Path) -> dict:
    m = {"title": "", "author": "", "date": "", "camera": "", "gps": ""}
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS

        img = Image.open(str(fp))
        exif = img._getexif() or {}
        tag = {v: k for k, v in TAGS.items()}
        m["author"] = str(exif.get(tag.get("Artist", 0), "")).strip()
        m["date"] = str(exif.get(tag.get("DateTime", 0), "")).strip()
        m["camera"] = str(exif.get(tag.get("Model", 0), "")).strip()
        gps_info = exif.get(tag.get("GPSInfo", 0), {})
        if gps_info:
            m["gps"] = str(gps_info)
        img.close()
    except Exception:
        pass
    return m


def get_metadata(fp: Path) -> dict:
    cat = file_category(fp)
    if cat == "pdf":
        return _pdf_meta(fp)
    if cat == "ebook":
        return _epub_meta(fp)
    if cat == "office":
        return _office_meta(fp)
    if cat == "image":
        return _image_exif(fp)
    return {"title": "", "author": ""}


# ─────────────────────────────────────────────────────────────────────────────
# EXIF EDITOR (modify/strip EXIF fields based on config)
# ─────────────────────────────────────────────────────────────────────────────
def apply_exif_edits(fp: Path, exif_cfg: dict, dry_run: bool = False):
    """
    exif_cfg keys (all optional, set to null/None to REMOVE, or string to SET):
      remove_gps       : bool  — strip GPS coordinates
      remove_device    : bool  — strip Make/Model/Software
      set_datetime     : str   — "YYYY:MM:DD HH:MM:SS" or null to remove
      set_author       : str   — Artist/Copyright or null to remove
      set_description  : str   — ImageDescription or null to remove
    """
    if not exif_cfg or file_category(fp) != "image":
        return
    try:
        import piexif
        import PIL
        from PIL import Image

        img = Image.open(str(fp))
        try:
            exif_dict = piexif.load(img.info.get("exif", b""))
        except Exception:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

        changed = False

        if exif_cfg.get("remove_gps"):
            exif_dict["GPS"] = {}
            changed = True

        if exif_cfg.get("remove_device"):
            for tag in [
                piexif.ImageIFD.Make,
                piexif.ImageIFD.Model,
                piexif.ImageIFD.Software,
                piexif.ImageIFD.HostComputer,
            ]:
                exif_dict["0th"].pop(tag, None)
            changed = True

        dt = exif_cfg.get("set_datetime")
        if "set_datetime" in exif_cfg:
            if dt:
                val = dt.encode()
                exif_dict["0th"][piexif.ImageIFD.DateTime] = val
                exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = val
                exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = val
            else:
                for d in ("0th", "Exif"):
                    for tag in (
                        piexif.ImageIFD.DateTime if d == "0th" else None,
                        piexif.ExifIFD.DateTimeOriginal,
                        piexif.ExifIFD.DateTimeDigitized,
                    ):
                        if tag:
                            exif_dict[d].pop(tag, None)
            changed = True

        author = exif_cfg.get("set_author")
        if "set_author" in exif_cfg:
            if author:
                exif_dict["0th"][piexif.ImageIFD.Artist] = author.encode()
                exif_dict["0th"][piexif.ImageIFD.Copyright] = author.encode()
            else:
                exif_dict["0th"].pop(piexif.ImageIFD.Artist, None)
                exif_dict["0th"].pop(piexif.ImageIFD.Copyright, None)
            changed = True

        desc = exif_cfg.get("set_description")
        if "set_description" in exif_cfg:
            if desc:
                exif_dict["0th"][piexif.ImageIFD.ImageDescription] = desc.encode()
            else:
                exif_dict["0th"].pop(piexif.ImageIFD.ImageDescription, None)
            changed = True

        if changed and not dry_run:
            exif_bytes = piexif.dump(exif_dict)
            img.save(str(fp), exif=exif_bytes)
            log.info(f"EXIF edited: '{fp.name}'")
        img.close()
    except ImportError:
        log.warning("piexif/Pillow not installed — EXIF editing skipped")
    except Exception as e:
        log.warning(f"EXIF edit failed '{fp.name}': {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SMART RENAME
# ─────────────────────────────────────────────────────────────────────────────
_JUNK = {
    "untitled",
    "unknown",
    "author",
    "n/a",
    "none",
    "",
    "microsoft word",
    "microsoft excel",
    "microsoft powerpoint",
    "openoffice",
}


def build_smart_name(fp: Path, meta: dict) -> Optional[str]:
    title = sanitize(meta.get("title", "")) if meta.get("title") else ""
    author = sanitize(meta.get("author", "")) if meta.get("author") else ""
    if title.lower() in _JUNK:
        title = ""
    if author.lower() in _JUNK:
        author = ""
    if title and author:
        stem = f"{author} - {title}"
    elif title:
        stem = title
    elif author:
        stem = f"{author} - {fp.stem}"
    else:
        return None
    return stem + fp.suffix


# ─────────────────────────────────────────────────────────────────────────────
# PLUGIN SYSTEM
# ─────────────────────────────────────────────────────────────────────────────
_plugins: list = []


def load_plugins(plugin_dir: str):
    """
    Load all .py files from plugin_dir.
    Each plugin must define:
        EXTENSIONS = [".pdf", ...] or ["*"] for all
        def rename(fp: Path, meta: dict) -> Optional[str]:
            # return new filename (with extension) or None to skip
    """
    global _plugins
    _plugins.clear()
    d = Path(plugin_dir)
    if not d.exists():
        return
    for f in d.glob("*.py"):
        try:
            spec = importlib.util.spec_from_file_location(f.stem, f)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "rename"):
                _plugins.append(module)
                log.info(f"Plugin loaded: '{f.name}'")
        except Exception as e:
            log.warning(f"Plugin load failed '{f.name}': {e}")


def apply_plugins(fp: Path, meta: dict) -> Optional[str]:
    for plugin in _plugins:
        exts = getattr(plugin, "EXTENSIONS", ["*"])
        if "*" in exts or fp.suffix.lower() in exts:
            try:
                result = plugin.rename(fp, meta)
                if result:
                    return result
            except Exception as e:
                log.warning(f"Plugin '{plugin.__name__}' error: {e}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# TRAVERSAL
# ─────────────────────────────────────────────────────────────────────────────
def traverse(root: Path, exclude: list = []) -> list:
    files = []
    try:
        for e in root.rglob("*"):
            if e.is_file() and not any(fnmatch.fnmatch(e.name, p) for p in exclude):
                files.append(e)
    except PermissionError as ex:
        log.warning(f"Permission: {ex}")
    except Exception as ex:
        log.error(f"Traverse error: {ex}")
    log.info(f"Traversed: {len(files)} files in '{root}'")
    return files


# ─────────────────────────────────────────────────────────────────────────────
# FOLDER-NAME RENAME (solo file only, zero subfolders)
# ─────────────────────────────────────────────────────────────────────────────
def folder_name_rename(fp: Path, dry_run: bool) -> Path:
    try:
        items = list(fp.parent.iterdir())
    except Exception:
        return fp
    files = [x for x in items if x.is_file()]
    dirs = [x for x in items if x.is_dir()]
    if len(files) != 1 or dirs or fp.stem == fp.parent.name:
        return fp
    new = fp.parent / (fp.parent.name + fp.suffix)
    if new.exists():
        return fp
    if not dry_run:
        fp.rename(new)
        log.info(f"Folder-rename: '{fp.name}' → '{new.name}'")
    else:
        log.info(f"[DRY] Folder-rename: '{fp.name}' → '{new.name}'")
    return new if not dry_run else fp


# ─────────────────────────────────────────────────────────────────────────────
# DEDUPLICATION  (exact + perceptual for images)
# ─────────────────────────────────────────────────────────────────────────────
def build_dup_sets(files: list, workers: int, quick: bool) -> tuple:
    """Returns (dupe_set, keeper_set)"""
    images = [f for f in files if file_category(f) == "image"]
    non_images = [f for f in files if file_category(f) != "image"]
    hash_map = defaultdict(list)

    # Non-images: size-bucket → hash
    size_map = defaultdict(list)
    for f in non_images:
        try:
            size_map[f.stat().st_size].append(f)
        except Exception:
            pass
    cands = [f for g in size_map.values() if len(g) > 1 for f in g]
    log.info(f"Exact-hash candidates: {len(cands)}/{len(non_images)}")

    limit = 4 << 20 if quick else 0  # quick mode: first 4MB only

    def _ht(fp):
        try:
            return fp, _compute_hash(fp, limit)
        except:
            return fp, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed({pool.submit(_ht, f): f for f in cands}):
            fp, h = fut.result()
            if h:
                hash_map[f"x:{h}"].append(fp)

    # Images: pHash
    log.info(f"pHash {len(images)} images...")

    def _ph(fp):
        try:
            import imagehash
            from PIL import Image

            return fp, str(
                imagehash.phash(Image.open(str(fp)).convert("RGB"), hash_size=16)
            )
        except Exception:
            return fp, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed({pool.submit(_ph, f): f for f in images}):
            fp, h = fut.result()
            if h:
                hash_map[f"p:{h}"].append(fp)

    dupe_set, keeper_set = set(), set()
    for paths in hash_map.values():
        if len(paths) < 2:
            continue
        ordered = sorted(paths, key=lambda p: p.stat().st_mtime if p.exists() else 1e18)
        keeper_set.add(ordered[0])
        for d in ordered[1:]:
            dupe_set.add(d)
        log.info(
            f"Keeper: '{ordered[0].name}' | dupes: {[x.name for x in ordered[1:]]}"
        )

    log.info(f"Dupe sets found: {len(dupe_set)} extra copies")
    return dupe_set, keeper_set


# ─────────────────────────────────────────────────────────────────────────────
# SECURE SHRED
# ─────────────────────────────────────────────────────────────────────────────
def _overwrite(fp: Path, passes: int):
    size = fp.stat().st_size
    if not size:
        return
    chunk = 1 << 20
    with open(fp, "r+b") as f:
        for i in range(passes):
            f.seek(0)
            done = 0
            blk = b"" if i == 0 else b"" if i == 1 else None
            while done < size:
                n = min(chunk, size - done)
                f.write(blk * n if blk else os.urandom(n))
                done += n
        f.flush()
        os.fsync(f.fileno())


def shred(fp: Path, passes: int, dry_run: bool):
    if dry_run:
        log.info(f"[DRY] Shred: '{fp}'")
        return
    try:
        _overwrite(fp, passes)
        ghost = fp.parent / (os.urandom(8).hex() + ".tmp")
        fp.rename(ghost)
        ghost.unlink()
        log.info(f"Shredded: '{fp.name}'")
    except Exception as e:
        log.error(f"Shred fail '{fp}': {e}")


def _clean_empty(folder: Path, stop: Path):
    cur = folder
    while cur != stop and cur != cur.parent:
        try:
            if not any(cur.iterdir()):
                cur.rmdir()
                log.info(f"Removed empty dir: '{cur.name}'")
                cur = cur.parent
            else:
                break
        except Exception:
            break


# ─────────────────────────────────────────────────────────────────────────────
# COPY → VERIFY → SHRED/DELETE  (copy integrity gate)
# ─────────────────────────────────────────────────────────────────────────────
def safe_move(
    src: Path,
    dst_dir: Path,
    root: Path,
    passes: int,
    dry_run: bool,
    new_name: str = None,
    do_shred: bool = True,
) -> Optional[Path]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    name = new_name or src.name
    dst = dst_dir / name
    if dst.exists():
        dst = dst_dir / f"{Path(name).stem}_{os.urandom(4).hex()}{Path(name).suffix}"

    if dry_run:
        log.info(f"[DRY] Move '{src.name}' → '{dst_dir.name}/{dst.name}'")
        return dst

    try:
        shutil.copy2(str(src), str(dst))

        # ── COPY INTEGRITY GATE ──────────────────────────────────────────────
        src_h = _compute_hash(src)
        dst_h = _compute_hash(dst)
        if src_h != dst_h:
            log.error(f"INTEGRITY FAIL: '{src}' hash mismatch — source NOT deleted!")
            dst.unlink(missing_ok=True)
            return None
        log.info(f"Integrity ✓  '{src.name}' → '{dst.name}'")
        # ────────────────────────────────────────────────────────────────────

        if do_shred:
            shred(src, passes, dry_run)
        else:
            src.unlink()
            log.info(f"Deleted: '{src.name}'")
        _clean_empty(src.parent, stop=root)
        return dst
    except Exception as e:
        log.error(f"safe_move failed '{src}': {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# DESTINATION DIRECTORY LOGIC
# ─────────────────────────────────────────────────────────────────────────────
def get_dst_dir(target: Path, fp: Path, is_dupe: bool, cfg: dict) -> Path:
    if not cfg.get("use_subfolders", True):
        return target
    mode = cfg.get("subfolder_mode", "unique_dupes")
    if mode == "flat":
        return target
    if mode == "by_type":
        return target / {
            "pdf": "pdf",
            "ebook": "ebooks",
            "office": "office",
            "image": "images",
            "other": "other",
        }.get(file_category(fp), "other")
    # unique_dupes (default)
    return target / ("duplicates" if is_dupe else "unique")


# ─────────────────────────────────────────────────────────────────────────────
# REPORTS
# ─────────────────────────────────────────────────────────────────────────────
def save_reports(report: dict, cfg: dict):
    if cfg.get("report_json", True):
        p = Path(cfg.get("report_json_path", "filevault_report.json"))
        p.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        log.info(f"JSON report → '{p}'")

    if cfg.get("report_csv", True):
        p = Path(cfg.get("report_csv_path", "filevault_moves.csv"))
        rows = report.get("moves", [])
        if rows:
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            log.info(f"CSV report → '{p}'")

    if cfg.get("report_html", True):
        p = Path(cfg.get("report_html_path", "filevault_report.html"))
        _write_html(report, p)
        log.info(f"HTML report → '{p}'")


def _write_html(r: dict, out: Path):
    moves = r.get("moves", [])
    renames = r.get("renames", [])
    stats = r.get("ext_stats", {})
    mode = "DRY-RUN" if r.get("dry_run") else "COMPLETED"

    def rows(data, keys):
        if not data:
            return f'<tr><td colspan="{len(keys)}">— none —</td></tr>'
        return "".join(
            "<tr>" + "".join(f"<td>{d.get(k,'')}</td>" for k in keys) + "</tr>"
            for d in data
        )

    ext_rows = "".join(
        f"<tr><td>{e}</td><td>{c}</td><td>{round(stats.get('size',{}).get(e,0)/1048576,2)}MB</td></tr>"
        for e, c in list(stats.get("count", {}).items())[:25]
    )
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>FileVault Report</title>
<style>
body{{font-family:Arial,sans-serif;background:#0d0d0d;color:#e0e0e0;padding:24px;margin:0}}
h1{{color:#00d4ff;margin-bottom:4px}}h2{{color:#aaffaa;border-bottom:1px solid #333;padding-bottom:4px;margin-top:28px}}
table{{border-collapse:collapse;width:100%;font-size:12px;margin-bottom:20px}}
th{{background:#1a1a2e;color:#00d4ff;padding:7px;text-align:left}}
td{{padding:5px 8px;border-bottom:1px solid #1e1e1e;word-break:break-all}}
tr:hover td{{background:#151515}}
.cards{{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 20px}}
.card{{background:#1a1a2e;border:1px solid #00d4ff22;border-radius:8px;padding:12px 20px;text-align:center;min-width:110px}}
.cv{{font-size:28px;color:#00d4ff;font-weight:bold}}.cl{{font-size:10px;color:#777}}
</style></head><body>
<h1>🗄️ FileVault v4.0 — {mode}</h1>
<p style="color:#666">Generated: {r.get("generated_at","")} | Engine: {HASH_ENGINE} | Passes: {r.get("shred_passes",7)}</p>
<div class="cards">
  <div class="card"><div class="cv">{r.get("total_files",0)}</div><div class="cl">Scanned</div></div>
  <div class="card"><div class="cv">{r.get("renamed_count",0)}</div><div class="cl">Renamed</div></div>
  <div class="card"><div class="cv">{r.get("unique_moved",0)}</div><div class="cl">Unique Moved</div></div>
  <div class="card"><div class="cv">{r.get("dupes_shredded",0)}</div><div class="cl">Dupes Shredded</div></div>
  <div class="card"><div class="cv">{r.get("elapsed",0)}s</div><div class="cl">Elapsed</div></div>
</div>
<h2>✏️ Renames ({len(renames)})</h2>
<table><tr><th>Original</th><th>New Name</th><th>Reason</th></tr>{rows(renames,["original","new_name","reason"])}</table>
<h2>📦 Moves ({len(moves)})</h2>
<table><tr><th>Action</th><th>Source</th><th>Destination</th><th>Category</th><th>Bytes</th></tr>
{rows(moves,["action","source","dest","category","size"])}</table>
<h2>📊 Extension Stats</h2>
<table><tr><th>Ext</th><th>Count</th><th>Size</th></tr>{ext_rows}</table>
</body></html>"""
    out.write_text(html, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# UNDO  (reverse last job from report)
# ─────────────────────────────────────────────────────────────────────────────
def undo_last_job(report_path: str = "filevault_report.json", dry_run: bool = False):
    p = Path(report_path)
    if not p.exists():
        log.error(f"No report found at '{p}'")
        return
    r = json.loads(p.read_text(encoding="utf-8"))
    moves = r.get("moves", [])
    undone = 0
    for m in reversed(moves):
        src = Path(m["dest"])
        dst = Path(m["source"])
        if not src.exists():
            log.warning(f"UNDO skip (gone): '{src}'")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dry_run:
            log.info(f"[DRY] UNDO: '{src}' → '{dst}'")
            continue
        try:
            shutil.move(str(src), str(dst))
            undone += 1
            log.info(f"UNDO: '{src.name}' → '{dst.parent.name}/'")
        except Exception as e:
            log.error(f"UNDO fail: {e}")
    log.info(f"Undo complete. {undone}/{len(moves)} files restored.")


# ─────────────────────────────────────────────────────────────────────────────
# WATCH MODE
# ─────────────────────────────────────────────────────────────────────────────
def watch_mode(cfg: dict):
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        log.error("pip install watchdog")
        return

    source = Path(cfg["source"])
    target = Path(cfg["target"])
    passes = cfg.get("passes", 7)
    dry_run = cfg.get("dry_run", False)

    class H(FileSystemEventHandler):
        def __init__(self):
            self._seen = set()
            log.info("Watch: building hash baseline...")
            for f in source.rglob("*"):
                if f.is_file():
                    try:
                        self._seen.add(_compute_hash(f))
                    except Exception:
                        pass
            log.info(f"Watch ready: {len(self._seen)} files in baseline")

        def on_created(self, event):
            if event.is_directory:
                return
            fp = Path(event.src_path)
            time.sleep(0.8)
            if not fp.exists():
                return
            try:
                h = _compute_hash(fp)
                is_dupe = h in self._seen
                self._seen.add(h)
                dst_dir = get_dst_dir(target, fp, is_dupe, cfg)
                safe_move(fp, dst_dir, source, passes, dry_run, do_shred=is_dupe)
                log.info(
                    f"[WATCH] {'Dupe' if is_dupe else 'Unique'}: '{fp.name}' → '{dst_dir}'"
                )
            except Exception as e:
                log.warning(f"[WATCH] error: {e}")

    obs = Observer()
    obs.schedule(H(), str(source), recursive=True)
    obs.start()
    log.info(f"Watch mode active on '{source}'. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────
def schedule_job(cfg: dict):
    """
    cfg["schedule"] can be:
      {"type": "once",    "at": "2026-03-05 02:00"}
      {"type": "interval","every_minutes": 60}
      {"type": "daily",   "at": "02:00"}
    """
    sched_cfg = cfg.get("schedule", {})
    stype = sched_cfg.get("type", "interval")

    def _run():
        log.info("[SCHEDULER] Triggering job...")
        _run_job(cfg)

    if stype == "once":
        at = datetime.datetime.strptime(sched_cfg["at"], "%Y-%m-%d %H:%M")
        now = datetime.datetime.now()
        delay = (at - now).total_seconds()
        if delay < 0:
            log.warning("[SCHEDULER] Scheduled time is in the past — running now")
            delay = 0
        log.info(f"[SCHEDULER] One-time job scheduled for {at} (in {delay:.0f}s)")
        t = threading.Timer(delay, _run)
        t.daemon = True
        t.start()
        t.join()

    elif stype == "daily":
        h, mn = map(int, sched_cfg.get("at", "02:00").split(":"))
        while True:
            now = datetime.datetime.now()
            nxt = now.replace(hour=h, minute=mn, second=0, microsecond=0)
            if nxt <= now:
                nxt += datetime.timedelta(days=1)
            delay = (nxt - now).total_seconds()
            log.info(f"[SCHEDULER] Next daily run at {nxt} (in {delay:.0f}s)")
            time.sleep(delay)
            _run()

    else:  # interval
        every = sched_cfg.get("every_minutes", 60) * 60
        log.info(f"[SCHEDULER] Interval job every {sched_cfg.get('every_minutes',60)}m")
        while True:
            _run()
            time.sleep(every)


# ─────────────────────────────────────────────────────────────────────────────
# WINDOWS CONTEXT MENU  (register/unregister)
# ─────────────────────────────────────────────────────────────────────────────
def register_context_menu(script_path: str):
    if platform.system() != "Windows":
        log.error("Context menu registration is Windows-only")
        return
    import winreg

    cmd = f'"{sys.executable}" "{script_path}" "%1" --gui'
    key_path = r"Directory\shell\FileVault\command"
    try:
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, key_path)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        # Add icon label
        parent = winreg.CreateKey(
            winreg.HKEY_CLASSES_ROOT, r"Directory\shell\FileVault"
        )
        winreg.SetValueEx(
            parent, "", 0, winreg.REG_SZ, "🗄️ FileVault — Organize this folder"
        )
        winreg.CloseKey(parent)
        log.info("Context menu registered. Right-click any folder to use FileVault.")
    except PermissionError:
        log.error("Run as Administrator to register context menu.")
    except Exception as e:
        log.error(f"Context menu error: {e}")


def unregister_context_menu():
    if platform.system() != "Windows":
        return
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\FileVault\command")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\FileVault")
        log.info("Context menu removed.")
    except Exception as e:
        log.error(f"Unregister error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# EXTENSION STATS
# ─────────────────────────────────────────────────────────────────────────────
def ext_stats(files: list) -> dict:
    cnt = defaultdict(int)
    sz = defaultdict(int)
    for f in files:
        e = f.suffix.lower() or "(none)"
        cnt[e] += 1
        try:
            sz[e] += f.stat().st_size
        except Exception:
            pass
    return {
        "count": dict(sorted(cnt.items(), key=lambda x: -x[1])),
        "size": dict(sorted(sz.items(), key=lambda x: -x[1])),
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN JOB ENGINE  ← single function called by CLI, GUI and scheduler
# ─────────────────────────────────────────────────────────────────────────────
def run_job(cfg: dict) -> dict:
    """
    THE single source of truth.
    cfg keys (all optional except source/target):
      source, target, dry_run, passes, workers, exclude,
      move_mode       : "all" | "unique" | "dupes"
      use_subfolders  : bool
      subfolder_mode  : "unique_dupes" | "by_type" | "flat"
      metadata_rename : bool
      rename_folder   : bool
      rename_date_prefix : bool
      shred_dupes     : bool
      shred_all       : bool  (shred even unique files after copy)
      quick_scan      : bool  (hash only first 4MB)
      exif_edits      : dict  (see apply_exif_edits)
      plugin_dir      : str
      report_json/csv/html : bool
      report_*_path   : str
    Returns report dict.
    """
    source = Path(cfg["source"]).resolve()
    target = Path(cfg["target"]).resolve()
    dry_run = bool(cfg.get("dry_run", False))
    passes = int(cfg.get("passes", 7))
    workers = int(cfg.get("workers", 8))
    exclude = list(cfg.get("exclude", []))
    move_mode = cfg.get("move_mode", "all")
    do_meta = bool(cfg.get("metadata_rename", True))
    do_folder = bool(cfg.get("rename_folder", True))
    do_date = bool(cfg.get("rename_date_prefix", False))
    shrd_dups = bool(cfg.get("shred_dupes", True))
    shrd_all = bool(cfg.get("shred_all", False))
    quick = bool(cfg.get("quick_scan", False))
    exif_cfg = cfg.get("exif_edits", {})
    plugin_d = cfg.get("plugin_dir", "")

    if plugin_d:
        load_plugins(plugin_d)

    t0 = time.perf_counter()
    log.info("=" * 70)
    log.info(f"  FileVault v4.0 | source={source} | target={target}")
    log.info(
        f"  mode={move_mode} | dry={dry_run} | passes={passes} | workers={workers}"
    )
    log.info(f"  hash_engine={HASH_ENGINE} | quick={quick}")
    log.info("=" * 70)

    if not source.exists():
        log.error(f"Source not found: '{source}'")
        return {}

    report = {
        "source": str(source),
        "target": str(target),
        "dry_run": dry_run,
        "shred_passes": passes,
        "generated_at": datetime.datetime.now().isoformat(),
        "moves": [],
        "renames": [],
        "total_files": 0,
        "renamed_count": 0,
        "unique_moved": 0,
        "dupes_shredded": 0,
        "elapsed": 0,
    }

    # 1. Traverse
    all_files = traverse(source, exclude)
    report["total_files"] = len(all_files)

    # 2. Folder-name renames
    if do_folder:
        updated = []
        for f in all_files:
            nf = folder_name_rename(f, dry_run)
            if nf != f:
                report["renames"].append(
                    {"original": str(f), "new_name": nf.name, "reason": "folder_name"}
                )
            updated.append(nf)
        all_files = updated

    # 3. Build duplicate sets
    dupe_set, keeper_set = build_dup_sets(all_files, workers, quick)

    # 4. Extension stats
    report["ext_stats"] = ext_stats(all_files)

    # 5. Process each file
    unique_moved = dupes_shredded = 0
    for fp in all_files:
        if not fp.exists():
            continue
        is_dupe = fp in dupe_set
        cat = file_category(fp)

        # ── Move mode filtering ────────────────────────────────────────────
        if move_mode == "unique" and is_dupe:
            # shred dupe in-place, do NOT copy to target
            shred(fp, passes, dry_run)
            dupes_shredded += 1
            report["moves"].append(
                {
                    "action": "dupe_shredded_in_place",
                    "source": str(fp),
                    "dest": "",
                    "category": cat,
                    "size": _safe_size(fp),
                }
            )
            continue
        if move_mode == "dupes" and not is_dupe:
            # leave unique file where it is
            continue

        # ── Smart rename ───────────────────────────────────────────────────
        new_name = None

        # Plugin rename (highest priority)
        if _plugins:
            meta = (
                get_metadata(fp)
                if (do_meta and cat in ("pdf", "ebook", "office", "image"))
                else {}
            )
            pname = apply_plugins(fp, meta)
            if pname:
                new_name = pname
                report["renames"].append(
                    {"original": fp.name, "new_name": pname, "reason": "plugin"}
                )

        # Metadata rename
        if not new_name and do_meta and cat in ("pdf", "ebook", "office"):
            meta = get_metadata(fp)
            proposed = build_smart_name(fp, meta)
            if proposed and proposed != fp.name:
                new_name = proposed
                report["renames"].append(
                    {
                        "original": fp.name,
                        "new_name": proposed,
                        "reason": f"metadata title='{meta.get('title','')}' author='{meta.get('author','')}')",
                    }
                )

        # EXIF date prefix for images
        if not new_name and do_date and cat == "image":
            meta = get_metadata(fp)
            dt_raw = meta.get("date", "")
            if dt_raw:
                date_str = dt_raw.replace(":", "-").split(" ")[0]
                new_name = f"{date_str}_{fp.name}"
                report["renames"].append(
                    {
                        "original": fp.name,
                        "new_name": new_name,
                        "reason": "exif_date_prefix",
                    }
                )

        # EXIF edits (before copy so destination has clean EXIF)
        if exif_cfg and cat == "image" and not dry_run:
            apply_exif_edits(fp, exif_cfg, dry_run)

        # ── Determine destination ──────────────────────────────────────────
        dst_dir = get_dst_dir(target, fp, is_dupe, cfg)
        do_shred = (is_dupe and shrd_dups) or shrd_all
        size = _safe_size(fp)

        dest = safe_move(
            fp, dst_dir, source, passes, dry_run, new_name=new_name, do_shred=do_shred
        )
        if dest:
            action = "dupe_moved" if is_dupe else "unique_moved"
            if is_dupe:
                dupes_shredded += 1
            else:
                unique_moved += 1
            report["moves"].append(
                {
                    "action": action,
                    "source": str(fp),
                    "dest": str(dest),
                    "category": cat,
                    "size": size,
                }
            )

    elapsed = round(time.perf_counter() - t0, 3)
    report.update(
        {
            "renamed_count": len(report["renames"]),
            "unique_moved": unique_moved,
            "dupes_shredded": dupes_shredded,
            "elapsed": elapsed,
        }
    )

    log.info("=" * 70)
    log.info(
        f"  DONE {elapsed}s | files={len(all_files)} renamed={report['renamed_count']}"
        f" unique={unique_moved} shredded={dupes_shredded}"
    )
    log.info("=" * 70)

    save_reports(report, cfg)
    return report


def _safe_size(fp: Path) -> int:
    try:
        return fp.stat().st_size
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG LOADER  (YAML → dict, with CLI override layer)
# ─────────────────────────────────────────────────────────────────────────────
def load_cfg(path: str) -> dict:
    try:
        import yaml

        with open(path) as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        log.warning(f"Config not found: {path}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def cli():
    p = argparse.ArgumentParser(
        prog="filevault",
        description="FileVault v4.0 — Smart file organizer, deduplicator & secure shredder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python filevault.py /src /tgt
  python filevault.py /src /tgt --dry-run
  python filevault.py /src /tgt --move-mode unique --no-subfolders
  python filevault.py /src /tgt --watch
  python filevault.py /src /tgt --schedule interval --every 60
  python filevault.py /src /tgt --undo
  python filevault.py --config filevault.yaml
  python filevault.py --register-context-menu
  python filevault.py --gui
        """,
    )
    p.add_argument("source", nargs="?")
    p.add_argument("target", nargs="?")
    p.add_argument("--config", help="YAML/JSON config file")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--passes", type=int, default=7)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--exclude", nargs="+", default=[], metavar="PATTERN")
    p.add_argument("--move-mode", choices=["all", "unique", "dupes"], default="all")
    p.add_argument(
        "--no-subfolders",
        action="store_true",
        help="Don't create sub-folders in target",
    )
    p.add_argument(
        "--subfolder-mode",
        choices=["unique_dupes", "by_type", "flat"],
        default="unique_dupes",
    )
    p.add_argument("--no-metadata-rename", action="store_true")
    p.add_argument("--no-folder-rename", action="store_true")
    p.add_argument(
        "--date-prefix", action="store_true", help="Prefix images with EXIF date"
    )
    p.add_argument("--no-shred-dupes", action="store_true")
    p.add_argument(
        "--shred-all", action="store_true", help="Shred even unique files after move"
    )
    p.add_argument(
        "--quick-scan", action="store_true", help="Hash only first 4MB (faster)"
    )
    p.add_argument("--watch", action="store_true")
    p.add_argument(
        "--schedule", choices=["once", "daily", "interval"], help="Schedule mode"
    )
    p.add_argument(
        "--at", help="Time for --schedule once/daily e.g. '02:00' or '2026-03-05 02:00'"
    )
    p.add_argument(
        "--every", type=int, default=60, help="Minutes for --schedule interval"
    )
    p.add_argument("--undo", action="store_true", help="Undo last job from report")
    p.add_argument(
        "--plugin-dir", default="", help="Directory with rename plugin .py files"
    )
    p.add_argument("--no-json", action="store_true")
    p.add_argument("--no-csv", action="store_true")
    p.add_argument("--no-html", action="store_true")
    p.add_argument("--log-file", default="filevault.log")
    p.add_argument(
        "--register-context-menu",
        action="store_true",
        help="Register Windows right-click menu",
    )
    p.add_argument("--unregister-context-menu", action="store_true")
    p.add_argument("--gui", action="store_true", help="Launch GUI")
    p.add_argument("--version", action="version", version="FileVault v4.0.0")
    args = p.parse_args()

    setup_logging(args.log_file)

    if args.register_context_menu:
        register_context_menu(__file__)
        return
    if args.unregister_context_menu:
        unregister_context_menu()
        return
    if args.gui:
        from filevault_gui import main as gui_main

        gui_main()
        return
    if args.undo:
        undo_last_job(dry_run=args.dry_run)
        return

    # Build cfg from YAML base + CLI overrides
    cfg = load_cfg(args.config) if args.config else {}
    if args.source:
        cfg["source"] = args.source
    if args.target:
        cfg["target"] = args.target
    if "source" not in cfg or "target" not in cfg:
        p.error("source and target required (via positional args or --config)")

    cfg.setdefault("passes", args.passes)
    cfg.setdefault("workers", args.workers)
    cfg["dry_run"] = args.dry_run or cfg.get("dry_run", False)
    cfg["move_mode"] = args.move_mode
    cfg["use_subfolders"] = not args.no_subfolders
    cfg["subfolder_mode"] = args.subfolder_mode
    cfg["metadata_rename"] = not args.no_metadata_rename and cfg.get(
        "metadata_rename", True
    )
    cfg["rename_folder"] = not args.no_folder_rename and cfg.get("rename_folder", True)
    cfg["rename_date_prefix"] = args.date_prefix or cfg.get("rename_date_prefix", False)
    cfg["shred_dupes"] = not args.no_shred_dupes and cfg.get("shred_dupes", True)
    cfg["shred_all"] = args.shred_all or cfg.get("shred_all", False)
    cfg["quick_scan"] = args.quick_scan or cfg.get("quick_scan", False)
    cfg["plugin_dir"] = args.plugin_dir or cfg.get("plugin_dir", "")
    cfg["exclude"] = cfg.get("exclude", []) + args.exclude
    cfg["report_json"] = not args.no_json and cfg.get("report_json", True)
    cfg["report_csv"] = not args.no_csv and cfg.get("report_csv", True)
    cfg["report_html"] = not args.no_html and cfg.get("report_html", True)

    if args.watch:
        watch_mode(cfg)
        return

    if args.schedule:
        sc = {"type": args.schedule}
        if args.at:
            sc["at"] = args.at
        if args.every:
            sc["every_minutes"] = args.every
        cfg["schedule"] = sc
        schedule_job(cfg)
        return

    run_job(cfg)


if __name__ == "__main__":
    cli()
