"""
Intelligent OCR + Information Extraction — Production Flask Application
With Secure Role-Based Admin Management, Real-Time Monitoring & Document Intelligence
"""

import contextlib
import os
import json
import logging
from functools import wraps
from flask import Flask, render_template, send_from_directory, jsonify, request, redirect, session, url_for
from werkzeug.serving import WSGIRequestHandler

from config import Config
from routes import api_bp, api_v1_bp, admin_bp, api_admin_bp
from routes.ocr_routes import find_job_record
from utils.progress_utils import get_progress
from services.auth_service import register_user, authenticate_user, get_user_by_id, update_user_password
from services.database import init_auth_db, get_active_db, log_activity

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)
logging.getLogger('werkzeug').setLevel(logging.WARNING)


class QuietRequestHandler(WSGIRequestHandler):
    """Suppress normal HTTP access noise."""
    def log_request(self, code='-', size='-'):
        return


def _enrich_job_for_results(job_data):
    """Ensure legacy job records include display-ready entities, tables, layout, and formatted text."""
    from services.document_intelligence import (
        detect_tables,
        build_unified_entities,
        build_document_formatted_view,
        build_structured_document_layout,
    )

    enriched = dict(job_data)
    raw_text = enriched.get("raw_text") or ""
    structured_data = enriched.get("structured_data") or {}
    extracted_fields = enriched.get("extracted_fields") or []
    spacy_entities = enriched.get("spacy_entities") or enriched.get("entities") or []

    # Normalize tables
    tables = enriched.get("tables") or []
    normalized_tables = []
    for table in tables:
        if isinstance(table, dict) and table.get("rows"):
            normalized_tables.append(table)
        elif isinstance(table, dict) and table.get("row"):
            normalized_tables.append(table)
        elif isinstance(table, str):
            normalized_tables.append({"headers": [], "rows": [[table]]})

    if not normalized_tables and raw_text.strip():
        normalized_tables = detect_tables(raw_text)
    enriched["tables"] = normalized_tables

    # Build unified entities from all available sources
    unified_entities = build_unified_entities(
        spacy_entities=spacy_entities,
        structured_data=structured_data,
        extracted_fields=extracted_fields,
    )
    enriched["entities"] = unified_entities
    enriched["spacy_entities"] = spacy_entities or [
        {"text": e["text"], "label": e["label"]} for e in unified_entities if e.get("source") == "ner"
    ]

    doc_type = enriched.get("document_type", "General Document")
    summary = enriched.get("summary") or enriched.get("ai_summary", "")
    layout_analysis = enriched.get("layout_analysis") or {}

    preferred_formatted = (
        enriched.get("formatted_text")
        or enriched.get("display_formatted_text")
        or enriched.get("formatted_document")
        or raw_text
    )
    if preferred_formatted and not enriched.get("display_formatted_text"):
        enriched["display_formatted_text"] = preferred_formatted
    elif not enriched.get("display_formatted_text"):
        enriched["display_formatted_text"] = build_document_formatted_view(
            doc_type, extracted_fields, structured_data, raw_text,
            normalized_tables, summary, unified_entities,
        )

    if not enriched.get("formatted_text") and enriched.get("display_formatted_text"):
        enriched["formatted_text"] = enriched["display_formatted_text"]

    if not enriched.get("formatted_html"):
        try:
            from services.layout_reconstruction import reconstruct_document_html
            page_layouts = enriched.get("page_layouts") or []
            enriched["formatted_html"] = reconstruct_document_html(
                page_layouts=page_layouts,
                raw_text=raw_text,
                structured_data=structured_data,
                tables=normalized_tables,
                doc_type=doc_type,
            )
        except Exception:
            enriched["formatted_html"] = ""
    enriched["display_formatted_html"] = enriched.get("formatted_html") or ""

    if not enriched.get("structured_layout"):
        enriched["structured_layout"] = build_structured_document_layout(
            doc_type, extracted_fields, structured_data, raw_text,
            normalized_tables, layout_analysis, unified_entities,
        )

    return enriched


def create_app():
    static_dir = os.path.join(Config.BASE_DIR, 'static')
    template_dir = os.path.join(Config.BASE_DIR, 'templates')
    app = Flask(__name__, static_folder=static_dir, static_url_path='/static', template_folder=template_dir)
    app.config.from_object(Config)

    # Initialize authentication database schema & default admin on startup
    init_auth_db()

    def current_user():
        """Resolve the signed-in account from the Flask session."""
        user_id = session.get("user_id")
        if not user_id:
            return None
        user = get_user_by_id(user_id)
        if not user or user.get("status") == "blocked":
            session.clear()
            return None
        return user

    def login_required(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if current_user():
                return view(*args, **kwargs)
            if request.path.startswith('/api') or request.is_json:
                return jsonify({"success": False, "message": "Authentication required."}), 401
            return redirect(url_for('auth_page', redirect=request.full_path.rstrip('?')))
        return wrapped_view

    @app.context_processor
    def inject_current_user():
        return {"current_user": current_user()}

    # Register API and Admin Blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(api_v1_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_admin_bp)

    # Ensure required storage directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['EXTRACTED_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

    # --- Jinja Template Filters ---
    @app.template_filter('pretty_json')
    def pretty_json_filter(data):
        if not data:
            return "{}"
        try:
            return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception:
            return str(data)
            
    @app.template_filter('clean_json')
    def clean_json_filter(data):
        from services.export_service import export_to_json
        if not data:
            return "{}"
        try:
            return export_to_json(data)
        except Exception:
            return "{}"

    @app.template_filter('job_json')
    def job_json_filter(data):
        """Full job payload for client-side rendering (excludes heavy OCR arrays)."""
        if not data:
            return "{}"
        payload = {
            "job_id": data.get("job_id") or data.get("id"),
            "filename": data.get("filename"),
            "document_type": data.get("document_type"),
            "summary": data.get("summary"),
            "ai_summary": data.get("ai_summary"),
            "raw_text": data.get("raw_text"),
            "formatted_text": data.get("formatted_text"),
            "display_formatted_text": data.get("display_formatted_text"),
            "structured_layout": data.get("structured_layout"),
            "entities": data.get("entities") or [],
            "spacy_entities": data.get("spacy_entities") or [],
            "tables": data.get("tables") or [],
            "structured_data": data.get("structured_data") or {},
            "extracted_fields": data.get("extracted_fields") or [],
            "layout_analysis": data.get("layout_analysis") or {},
            "ai_insights_structured": data.get("ai_insights_structured") or {},
            "confidence_score": data.get("confidence_score"),
            "engine": data.get("engine"),
            "processing_time": data.get("processing_time"),
            "saved_file_name": data.get("saved_file_name"),
            "formatted_html": data.get("formatted_html") or data.get("display_formatted_html") or "",
            "display_formatted_html": data.get("display_formatted_html") or data.get("formatted_html") or "",
        }
        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            return "{}"

    # --- HTML Page Routes ---
    @app.route('/')
    def home():
        return render_template('index.html')

    @app.route('/upload')
    @login_required
    def upload_page():
        return render_template('upload.html')

    @app.route('/settings')
    @login_required
    def settings_page():
        return render_template('settings.html')

    def _get_unique_jobs():
        jobs = []
        seen = set()
        for folder in [app.config['EXTRACTED_FOLDER'], app.config['OUTPUT_FOLDER']]:
            if os.path.exists(folder):
                for fn in os.listdir(folder):
                    if fn.endswith('.json') and not fn.startswith('cache_'):
                        filepath = os.path.join(folder, fn)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                jid = data.get('job_id') or data.get('id') or fn.replace('.json', '')
                                if jid in seen:
                                    continue
                                seen.add(jid)
                                jobs.append(data)
                        except Exception:
                            pass
        jobs.sort(key=lambda x: str(x.get('timestamp', x.get('upload_time', ''))), reverse=True)
        return jobs

    @app.route('/results')
    @app.route('/results/<job_id>')
    @login_required
    def results_page(job_id=None):
        if not job_id and not request.is_json and 'application/json' not in request.headers.get('Accept', ''):
            recent_jobs = _get_unique_jobs()
            if recent_jobs:
                latest_id = recent_jobs[0].get('job_id') or recent_jobs[0].get('id')
                if latest_id:
                    return redirect(url_for('results_page', job_id=latest_id))

        job_data = None
        if job_id:
            job_data = find_job_record(app.config, job_id)
            if job_data:
                job_data = _enrich_job_for_results(job_data)

        # Handle API / JSON requests
        if request.is_json or 'application/json' in request.headers.get('Accept', ''):
            if job_data:
                return jsonify({
                    "success": True,
                    "job_id": job_id,
                    "status": "completed",
                    "document": {
                        "filename": job_data.get("filename", "Document"),
                        "document_type": job_data.get("document_type", "Unknown")
                    },
                    "extracted_data": job_data.get("structured_data", {}),
                    "important_values": job_data.get("spacy_entities", {}),
                    "key_findings": job_data.get("extracted_fields", []),
                    "ai_summary": job_data.get("summary", ""),
                    "raw_json": job_data
                }), 200

            progress = get_progress(job_id) if job_id else {}
            if progress.get("status") in ["processing", "started", "queued"]:
                return jsonify({
                    "success": True,
                    "job_id": job_id,
                    "status": "processing",
                    "percent": progress.get("percent", 15),
                    "message": progress.get("message", "Processing document...")
                }), 200

            return jsonify({
                "success": False,
                "job_id": job_id,
                "status": "not_found",
                "message": f"Result not found for Job ID: {job_id}"
            }), 404

        # Browser HTML Page Request
        return render_template('dashboard.html', job=job_data, job_id=job_id)

    @app.route('/history')
    @login_required
    def history_page():
        jobs = _get_unique_jobs()
        return render_template('history.html', jobs=jobs)

    @app.route('/auth')
    def auth_page():
        user = current_user()
        portal = request.args.get('portal', request.args.get('mode', 'user'))
        if user:
            if user.get("role") == "admin":
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('dashboard_page'))
        return render_template('auth.html', default_portal=portal)

    @app.route('/register')
    def register_page():
        user = current_user()
        if user:
            if user.get("role") == "admin":
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('dashboard_page'))
        return render_template('register.html')

    @app.route('/auth/login', methods=['POST'])
    def login_auth():
        if request.is_json:
            payload = request.get_json(silent=True) or {}
        else:
            payload = request.form.to_dict() or request.get_json(silent=True) or {}

        email = payload.get('email', '')
        password = payload.get('password', '')
        portal = payload.get('portal', 'user')

        user, error = authenticate_user(email, password, portal=portal, ip_address=request.remote_addr)
        if user:
            session.clear()
            session['user_id'] = user['id']
            session['role'] = user['role']

            redirect_target = "/admin/dashboard" if user["role"] == "admin" else "/dashboard"
            return jsonify({
                "success": True,
                "message": f"Welcome back, {user['name']}!",
                "user": user,
                "redirect": redirect_target
            }), 200

        status_code = 403 if error and "denied" in error.lower() else (500 if error and "unavailable" in error.lower() else 401)
        return jsonify({"success": False, "message": error or "Invalid email or password."}), status_code

    @app.route('/auth/register', methods=['POST'])
    def register_auth():
        if request.is_json:
            payload = request.get_json(silent=True) or {}
        else:
            payload = request.form.to_dict() or request.get_json(silent=True) or {}

        name = payload.get('name', '')
        email = payload.get('email', '')
        password = payload.get('password', '')

        user, error = register_user(name, email, password)
        if user:
            session.clear()
            session['user_id'] = user['id']
            session['role'] = user['role']
            return jsonify({
                "success": True,
                "message": f"Account created for {user['name']}!",
                "user": user,
                "redirect": "/dashboard"
            }), 201

        status_code = 500 if error and "unavailable" in error.lower() else 400
        return jsonify({"success": False, "message": error or "Registration failed."}), status_code

    @app.route('/auth/logout', methods=['POST', 'GET'])
    def logout_auth():
        session.clear()
        if request.method == 'GET' or 'text/html' in request.headers.get('Accept', ''):
            return redirect(url_for('home'))
        return jsonify({"success": True, "message": "You have been logged out.", "redirect": "/"})

    @app.route('/auth/session', methods=['GET'])
    def auth_session():
        user = current_user()
        return jsonify({"authenticated": bool(user), "user": user})

    @app.route('/api/user/update-password', methods=['POST'])
    @login_required
    def update_password_api():
        """Change logged-in user's password via Settings page."""
        user = current_user()
        if not user:
            return jsonify({"success": False, "message": "Not authenticated."}), 401
        payload = request.get_json(silent=True) or {}
        current_pw = payload.get('current_password', '').strip()
        new_pw = payload.get('new_password', '').strip()
        if not current_pw or not new_pw:
            return jsonify({"success": False, "message": "Both current and new password are required."}), 400
        if len(new_pw) < 8:
            return jsonify({"success": False, "message": "New password must be at least 8 characters."}), 400
        ok, msg = update_user_password(user['id'], current_pw, new_pw)
        log_activity("Password changed", user_id=user['id'])
        return jsonify({"success": ok, "message": msg}), (200 if ok else 400)

    @app.route('/dashboard')
    @login_required
    def dashboard_page():
        return render_template('dashboard_overview.html', user=current_user())

    @app.route('/about')
    def about_page():
        return render_template('about.html')

    @app.route('/uploads/<filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # --- Global Error Handlers ---
    @app.errorhandler(400)
    def bad_request_error(e):
        return jsonify({"success": False, "message": getattr(e, 'description', 'Bad Request')}), 400

    @app.errorhandler(403)
    def forbidden_error(e):
        if request.path.startswith('/api') or request.is_json:
            return jsonify({"success": False, "message": "Access forbidden: insufficient privileges."}), 403
        return render_template('admin/unauthorized.html'), 403

    @app.errorhandler(404)
    def not_found_error(e):
        if request.path.startswith('/api') or request.is_json:
            return jsonify({"success": False, "message": "Resource not found"}), 404
        return render_template('admin/not_found.html'), 404

    @app.errorhandler(413)
    def file_too_large_error(e):
        return jsonify({"success": False, "message": "File size exceeds 16MB limit."}), 413

    @app.errorhandler(500)
    def internal_server_error(e):
        logging.exception("Unhandled server exception: %s", e)
        if request.path.startswith('/results') or 'text/html' in request.headers.get('Accept', ''):
            return render_template('dashboard.html', job=None, error_message="An unexpected error occurred while loading document results. Please try uploading your document again."), 200
        return jsonify({"success": False, "message": "Internal server error.", "error": str(e)}), 500

    return app

app = create_app()


def _find_free_port(start=5000, attempts=20):
    import socket
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return start


def _open_browser(url, delay=1.5):
    import threading
    import time
    import webbrowser

    def _launch():
        time.sleep(delay)
        webbrowser.open(url)

    threading.Thread(target=_launch, daemon=True).start()


if __name__ == '__main__':
    port = _find_free_port(5000)
    url = f'http://127.0.0.1:{port}'

    print()
    print('=' * 54)
    print('  AI Document Intelligence Platform — Server Started')
    print('=' * 54)
    print()
    print(f'  Local URL:       {url}')
    print(f'  Upload:          {url}/upload')
    print(f'  Results:         {url}/results')
    print(f'  Dashboard:       {url}/dashboard')
    print(f'  Admin Portal:    {url}/admin/dashboard')
    print()
    print('=' * 54)

    _open_browser(url)
    app.run(
        debug=False,
        host='127.0.0.1',
        port=port,
        use_reloader=False,
        threaded=True,
        request_handler=QuietRequestHandler,
    )
