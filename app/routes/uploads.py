from flask import Blueprint, current_app, send_from_directory, send_file, abort
import os
from io import BytesIO

from ..models import ImageAsset

uploads_bp = Blueprint("uploads", __name__)


@uploads_bp.route("/uploads/<path:filename>")
def serve_upload(filename: str):
    """
    Servir archivos subidos desde el directorio configurado.

    Pensado para entornos como Render donde UPLOADS_DIR puede estar
    fuera de static/.
    """
    uploads_dir = current_app.config.get("UPLOADS_DIR", "./uploads")
    # Aseguramos que el directorio exista incluso si se llama antes de guardar
    os.makedirs(uploads_dir, exist_ok=True)
    path = os.path.join(uploads_dir, filename)
    if os.path.exists(path):
        return send_from_directory(uploads_dir, filename)
    asset = ImageAsset.query.filter_by(filename=filename).first()
    if not asset:
        abort(404)
    return send_file(BytesIO(asset.data), mimetype=asset.content_type, download_name=filename)
