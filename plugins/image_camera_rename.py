# plugins/image_camera_rename.py
# Rename images to: CameraModel_YYYY-MM-DD_originalname.jpg

from pathlib import Path
from typing import Optional

EXTENSIONS = [".jpg", ".jpeg", ".png", ".heic"]

def rename(fp: Path, meta: dict) -> Optional[str]:
    camera = meta.get("camera","").strip().replace(" ","_")
    date   = meta.get("date","").replace(":","_").replace(" ","_")[:10]
    if camera and date:
        return f"{camera}_{date}_{fp.name}"
    if date:
        return f"{date}_{fp.name}"
    return None
