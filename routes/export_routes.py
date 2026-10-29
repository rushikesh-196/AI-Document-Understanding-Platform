"""
Export API Routes (JSON, CSV, DOCX, PDF, Excel)
"""

import os
import json
import re
from flask import jsonify, request, current_app, send_file, session
import io
from . import api_bp, api_v1_bp
from services.export_service import export_to_json, export_to_csv, export_to_docx, export_to_pdf, export_to_excel, export_to_txt
from routes.ocr_routes import find_job_record

def get_job_record(job_id):
    return find_job_record(current_app.config, job_id)

def get_safe_export_filename(job_data, ext):
    raw_name = job_data.get('filename') or 'document'
    safe_base = os.path.basename(raw_name)
    safe_base = re.sub(r'[\r\n"\']+', '', safe_base).strip() or "document"
    return f"AI_OCR_Report_{safe_base}.{ext}"

@api_bp.route('/export/<fmt>', methods=['GET'])
@api_v1_bp.route('/export/<fmt>', methods=['GET'])
@api_bp.route('/export/<fmt>/<job_id>', methods=['GET'])
@api_v1_bp.route('/export/<fmt>/<job_id>', methods=['GET'])
def export_file(fmt, job_id=None):
    if not session.get('user_id'):
        return jsonify({"success": False, "message": "Authentication required."}), 401

    if not job_id:
        job_id = request.args.get('id') or request.args.get('job_id')
    if not job_id:
        extracted_folder = current_app.config['EXTRACTED_FOLDER']
        if os.path.exists(extracted_folder):
            files = [f for f in os.listdir(extracted_folder) if f.endswith('.json') and not f.startswith('cache_')]
            if files:
                files.sort(key=lambda x: os.path.getmtime(os.path.join(extracted_folder, x)), reverse=True)
                job_id = files[0].replace('.json', '')

    job_data = get_job_record(job_id)
    if not job_data:
        return jsonify({"success": False, "message": "Record not found."}), 404

    owner_id = job_data.get('user_id') or job_data.get('owner_id') or job_data.get('uploaded_by')
    if owner_id and str(owner_id) != str(session.get('user_id')):
        return jsonify({"success": False, "message": "Access denied."}), 403

    fmt = fmt.lower()
    if fmt in ['txt', 'text']:
        content = export_to_txt(job_data)
        bio = io.BytesIO(content.encode('utf-8'))
        bio.seek(0)
        filename = get_safe_export_filename(job_data, "txt")
        return send_file(bio, mimetype="text/plain; charset=utf-8", download_name=filename, as_attachment=True)

    elif fmt == 'json':
        content = export_to_json(job_data)
        bio = io.BytesIO(content.encode('utf-8'))
        bio.seek(0)
        filename = get_safe_export_filename(job_data, "json")
        return send_file(bio, mimetype="application/json", download_name=filename, as_attachment=True)

    elif fmt in ['csv', 'excel', 'xlsx']:
        if fmt == 'csv':
            content = export_to_csv(job_data)
            bio = io.BytesIO(content.encode('utf-8-sig'))
            filename = get_safe_export_filename(job_data, "csv")
            mimetype = "text/csv; charset=utf-8"
        else:
            excel_bytes = export_to_excel(job_data)
            bio = io.BytesIO(excel_bytes)
            filename = get_safe_export_filename(job_data, "xlsx")
            mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        bio.seek(0)
        return send_file(bio, mimetype=mimetype, download_name=filename, as_attachment=True)

    elif fmt == 'docx':
        try:
            docx_bytes = export_to_docx(job_data)
            bio = io.BytesIO(docx_bytes)
            bio.seek(0)
            filename = get_safe_export_filename(job_data, "docx")
            return send_file(bio, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document", download_name=filename, as_attachment=True)
        except Exception as e:
            current_app.logger.error(f"DOCX export error: {e}", exc_info=True)
            return jsonify({"success": False, "message": f"DOCX generation failed: {str(e)}"}), 500

    elif fmt == 'pdf':
        try:
            pdf_bytes = export_to_pdf(job_data)
            bio = io.BytesIO(pdf_bytes)
            bio.seek(0)
            filename = get_safe_export_filename(job_data, "pdf")
            return send_file(bio, mimetype="application/pdf", download_name=filename, as_attachment=True)
        except Exception as e:
            current_app.logger.error(f"PDF export error: {e}", exc_info=True)
            return jsonify({"success": False, "message": f"PDF generation failed: {str(e)}"}), 500

    return jsonify({"success": False, "message": "Unsupported export format."}), 400

@api_v1_bp.route('/download/<job_id>/<fmt>', methods=['GET'])
def download_export_v1(job_id, fmt):
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    job_data = get_job_record(job_id)
    if not job_data:
        return jsonify({"status": "error", "message": "Job not found"}), 404

    owner_id = job_data.get('user_id') or job_data.get('owner_id') or job_data.get('uploaded_by')
    if owner_id and str(owner_id) != str(session.get('user_id')):
        return jsonify({"status": "error", "message": "Access denied."}), 403

    fmt = fmt.lower()
    if fmt in ['txt', 'text']:
        content = export_to_txt(job_data)
        bio = io.BytesIO(content.encode('utf-8'))
        bio.seek(0)
        filename = get_safe_export_filename(job_data, "txt")
        return send_file(bio, mimetype="text/plain; charset=utf-8", download_name=filename, as_attachment=True)

    elif fmt == 'json':
        content = export_to_json(job_data)
        bio = io.BytesIO(content.encode('utf-8'))
        bio.seek(0)
        filename = get_safe_export_filename(job_data, "json")
        return send_file(bio, mimetype="application/json", download_name=filename, as_attachment=True)

    elif fmt in ['csv', 'excel', 'xlsx']:
        if fmt == 'csv':
            content = export_to_csv(job_data)
            bio = io.BytesIO(content.encode('utf-8-sig'))
            filename = get_safe_export_filename(job_data, "csv")
            mimetype = "text/csv; charset=utf-8"
        else:
            excel_bytes = export_to_excel(job_data)
            bio = io.BytesIO(excel_bytes)
            filename = get_safe_export_filename(job_data, "xlsx")
            mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        bio.seek(0)
        return send_file(bio, mimetype=mimetype, download_name=filename, as_attachment=True)

    elif fmt == 'docx':
        try:
            docx_bytes = export_to_docx(job_data)
            bio = io.BytesIO(docx_bytes)
            bio.seek(0)
            filename = get_safe_export_filename(job_data, "docx")
            return send_file(bio, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document", download_name=filename, as_attachment=True)
        except Exception as e:
            current_app.logger.error(f"DOCX export error: {e}", exc_info=True)
            return jsonify({"status": "error", "message": f"DOCX generation failed: {str(e)}"}), 500

    elif fmt == 'pdf':
        try:
            pdf_bytes = export_to_pdf(job_data)
            bio = io.BytesIO(pdf_bytes)
            bio.seek(0)
            filename = get_safe_export_filename(job_data, "pdf")
            return send_file(bio, mimetype="application/pdf", download_name=filename, as_attachment=True)
        except Exception as e:
            current_app.logger.error(f"PDF export error: {e}", exc_info=True)
            return jsonify({"status": "error", "message": f"PDF generation failed: {str(e)}"}), 500

    return jsonify({"status": "error", "message": "Unsupported format"}), 400

