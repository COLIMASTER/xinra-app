import os
import secrets
from PIL import Image
from flask import current_app, url_for


ALLOWED_EXTS = {"jpg", "jpeg", "png"}


def _secure_ext(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext if ext in ALLOWED_EXTS else "jpg"


def process_and_save_image(file_storage):
    max_mb = int(current_app.config.get("MAX_IMAGE_MB", 2))
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > max_mb * 1024 * 1024:
        raise ValueError("Image exceeds size limit")

    img = Image.open(file_storage.stream)
    img = img.convert("RGB") if img.mode in ("P", "RGBA") else img

    max_side = 1600
    w, h = img.size
    if max(w, h) > max_side:
        if w > h:
            new_w = max_side
            new_h = int(h * (max_side / w))
        else:
            new_h = max_side
            new_w = int(w * (max_side / h))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        w, h = img.size

    ext = _secure_ext(file_storage.filename or "")
    name = f"{secrets.token_hex(8)}.{ext}"
    uploads_dir = current_app.config.get("UPLOADS_DIR", "./uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    path = os.path.join(uploads_dir, name)
    img.save(path, format="JPEG" if ext in {"jpg", "jpeg"} else "PNG", optimize=True, quality=85)

    # URL pública servida por el blueprint de uploads
    try:
        url = url_for("uploads.serve_upload", filename=name)
    except RuntimeError:
        # En contextos sin petición (por ejemplo scripts) devolvemos ruta relativa
        url = f"/uploads/{name}"
    return url, w, h
