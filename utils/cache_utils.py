"""
Cache Manager for OCR Results
"""

import hashlib
import json
import os
from config import Config

def compute_file_hash(file_path):
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_cached_result(file_hash):
    if not Config.ENABLE_CACHE:
        return None
    cache_file = os.path.join(Config.EXTRACTED_FOLDER, f"cache_{file_hash}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None

def set_cached_result(file_hash, data):
    os.makedirs(Config.EXTRACTED_FOLDER, exist_ok=True)
    cache_file = os.path.join(Config.EXTRACTED_FOLDER, f"cache_{file_hash}.json")
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
