"""
History Management API Routes
"""

import os
import json
from flask import jsonify, current_app
from . import api_bp, api_v1_bp

@api_bp.route('/history', methods=['GET'])
@api_v1_bp.route('/jobs', methods=['GET'])
def get_history():
    extracted_folder = current_app.config['EXTRACTED_FOLDER']
    outputs_folder = current_app.config['OUTPUT_FOLDER']
    os.makedirs(extracted_folder, exist_ok=True)

    records = []
    seen_ids = set()

    for folder in [extracted_folder, outputs_folder]:
        if not os.path.exists(folder):
            continue
        for fn in os.listdir(folder):
            if fn.endswith('.json') and not fn.startswith('cache_'):
                filepath = os.path.join(folder, fn)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        job_id = data.get("job_id") or data.get("id") or fn.replace('.json', '')
                        if job_id in seen_ids:
                            continue
                        seen_ids.add(job_id)

                        records.append({
                            "id": job_id,
                            "job_id": job_id,
                            "filename": data.get("filename", fn),
                            "upload_time": data.get("upload_time", data.get("timestamp", "N/A")),
                            "document_type": data.get("document_type", "Unknown"),
                            "confidence": data.get("confidence", data.get("confidence_score", 0.0)),
                            "confidence_score": data.get("confidence_score", f"{data.get('confidence', 0)}%"),
                            "summary": data.get("summary", ""),
                            "structured_data": data.get("structured_data", {}),
                            "extracted_fields": data.get("extracted_fields", [])
                        })
                except Exception:
                    pass

    records.sort(key=lambda x: str(x.get("upload_time", "")), reverse=True)

    return jsonify({
        "success": True,
        "count": len(records),
        "history": records,
        "jobs": records
    }), 200

@api_bp.route('/history/<job_id>', methods=['DELETE'])
@api_v1_bp.route('/job/<job_id>', methods=['DELETE'])
def delete_history_record(job_id):
    extracted_folder = current_app.config['EXTRACTED_FOLDER']
    outputs_folder = current_app.config['OUTPUT_FOLDER']
    uploads_folder = current_app.config['UPLOAD_FOLDER']

    deleted = False

    for folder in [extracted_folder, outputs_folder]:
        fp = os.path.join(folder, f"{job_id}.json")
        if os.path.exists(fp):
            os.remove(fp)
            deleted = True

    if os.path.exists(uploads_folder):
        for fn in os.listdir(uploads_folder):
            if fn.startswith(job_id):
                os.remove(os.path.join(uploads_folder, fn))

    if deleted:
        return jsonify({
            "success": True,
            "status": "success",
            "message": f"History record {job_id} deleted successfully."
        }), 200

    return jsonify({
        "success": False,
        "status": "error",
        "message": "Record not found."
    }), 404
