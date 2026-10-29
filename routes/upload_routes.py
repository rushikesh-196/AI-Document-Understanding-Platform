"""
File Upload API Routes
"""

import os
import uuid
from flask import jsonify, request, current_app
from . import api_bp, api_v1_bp
from utils.file_utils import allowed_file, sanitize_file_name, is_valid_file_size

@api_bp.route('/upload', methods=['POST'])
@api_v1_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file uploaded."}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"success": False, "message": "No file selected."}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "message": "Unsupported file type."}), 400

    clean_filename = sanitize_file_name(file.filename)
    unique_id = uuid.uuid4().hex[:8].upper()
    saved_filename = f"{unique_id}_{clean_filename}"

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    saved_path = os.path.join(upload_folder, saved_filename)

    file.save(saved_path)

    if not is_valid_file_size(saved_path, current_app.config['MAX_CONTENT_LENGTH']):
        os.remove(saved_path)
        return jsonify({"success": False, "message": "File size exceeds maximum allowed limit (16MB)."}), 400

    return jsonify({
        "success": True,
        "filename": saved_filename,
        "original_filename": clean_filename,
        "status": "uploaded"
    }), 200
