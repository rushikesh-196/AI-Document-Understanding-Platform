"""
File Security & Validation Utilities
"""

import os
from werkzeug.utils import secure_filename
from config import Config

def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in Config.ALLOWED_EXTENSIONS

def sanitize_file_name(filename):
    clean_name = secure_filename(filename)
    if not clean_name:
        clean_name = "uploaded_document"
    return clean_name

def is_valid_file_size(file_path, max_bytes=Config.MAX_CONTENT_LENGTH):
    if not os.path.exists(file_path):
        return False
    return os.path.getsize(file_path) <= max_bytes
