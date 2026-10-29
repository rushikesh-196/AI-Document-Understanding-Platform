"""
Admin Management & Monitoring Routes
Provides secure Web UI pages and REST APIs strictly for administrators.
"""

from functools import wraps
import os

from flask import Blueprint, render_template, request, jsonify, redirect, session, url_for, current_app, send_from_directory

from services.auth_service import (
    get_user_by_id,
    create_user_by_admin,
    update_user_status,
    delete_user_by_admin,
    get_admin_managed_users,
    update_user_password,
)
from services.admin_service import (
    get_admin_dashboard_stats,
    get_admin_dashboard_data,
    get_admin_notifications,
    get_admin_documents,
    get_admin_document_detail,
    get_admin_document_filter_options,
    delete_document_by_admin,
    get_admin_analytics,
    get_admin_processing_monitor,
    get_admin_activity_logs,
    get_admin_error_logs,
    get_admin_storage_breakdown,
)
from services.auth_service import update_admin_profile

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
api_admin_bp = Blueprint("api_admin", __name__, url_prefix="/api/admin")


def admin_required(view):
    """Decorator ensuring that the logged-in user possesses role='admin'."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            if request.path.startswith("/api") or request.is_json:
                return jsonify({"success": False, "message": "Authentication required."}), 401
            return redirect(url_for("auth_page", portal="admin", redirect=request.full_path.rstrip("?")))

        user = get_user_by_id(user_id)
        if not user or user.get("role") != "admin":
            if request.path.startswith("/api") or request.is_json:
                return jsonify({"success": False, "message": "Access denied: Administrator privileges required."}), 403
            return render_template("admin/unauthorized.html"), 403

        if user.get("status") == "blocked":
            session.clear()
            if request.path.startswith("/api") or request.is_json:
                return jsonify({"success": False, "message": "Your administrator account has been suspended."}), 403
            return redirect(url_for("auth_page", portal="admin"))

        return view(*args, **kwargs)
    return wrapped_view


def get_current_admin():
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = get_user_by_id(user_id)
    if user and user.get("role") == "admin":
        return user
    return None


# ==============================================================================
# ADMIN HTML PAGE ROUTES
# ==============================================================================

@admin_bp.route("/")
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    admin = get_current_admin()
    return render_template("admin/dashboard.html", admin=admin, active_page="dashboard")


@admin_bp.route("/users")
@admin_required
def users_page():
    admin = get_current_admin()
    search = request.args.get("q", "").strip()
    users = get_admin_managed_users(admin["id"], search_query=search)
    return render_template("admin/users.html", admin=admin, users=users, search=search, active_page="users")


@admin_bp.route("/documents")
@admin_required
def documents_page():
    admin = get_current_admin()
    search = request.args.get("q", "").strip()
    doc_type = request.args.get("type", "ALL")
    status = request.args.get("status", "ALL")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    page = max(1, int(request.args.get("page", 1)))

    doc_data = get_admin_documents(admin["id"], search=search, doc_type=doc_type, status=status, page=page, limit=20, date_from=date_from or None, date_to=date_to or None)
    filter_options = get_admin_document_filter_options(admin["id"])
    return render_template(
        "admin/documents.html",
        admin=admin,
        documents=doc_data["documents"],
        total=doc_data["total"],
        page=doc_data["page"],
        total_pages=doc_data["total_pages"],
        search=search,
        selected_type=doc_type,
        selected_status=status,
        date_from=date_from,
        date_to=date_to,
        filter_options=filter_options,
        active_page="documents",
    )


@admin_bp.route("/processing-monitor")
@admin_required
def processing_monitor_page():
    admin = get_current_admin()
    monitor_data = get_admin_processing_monitor(admin["id"])
    return render_template(
        "admin/processing_monitor.html",
        admin=admin,
        monitor=monitor_data,
        active_page="processing-monitor",
    )


@admin_bp.route("/analytics")
@admin_required
def analytics_page():
    admin = get_current_admin()
    snapshot = get_admin_dashboard_data(admin["id"])
    analytics_data = {
        "volume_timeline": snapshot["analytics"]["upload_timeline"],
        "registration_timeline": snapshot["analytics"]["registration_timeline"],
        "type_distribution": snapshot["analytics"]["type_distribution"],
        "status_distribution": snapshot["analytics"]["status_distribution"],
        "user_activity_ranking": snapshot["analytics"]["user_activity"],
    }
    return render_template(
        "admin/analytics.html",
        admin=admin,
        analytics=analytics_data,
        active_page="analytics",
    )


@admin_bp.route("/activity-logs")
@admin_required
def activity_logs_page():
    admin = get_current_admin()
    action = request.args.get("action")
    logs = get_admin_activity_logs(admin["id"], action_filter=action, limit=150)
    return render_template(
        "admin/activity_logs.html",
        admin=admin,
        logs=logs,
        selected_action=action or "ALL",
        active_page="activity-logs",
    )


@admin_bp.route("/error-logs")
@admin_required
def error_logs_page():
    admin = get_current_admin()
    stage = request.args.get("stage")
    error_type = request.args.get("error_type")
    logs = get_admin_error_logs(admin["id"], stage_filter=stage, error_type_filter=error_type, limit=150)
    return render_template(
        "admin/error_logs.html",
        admin=admin,
        logs=logs,
        selected_stage=stage or "ALL",
        selected_error_type=error_type or "ALL",
        active_page="error-logs",
    )


@admin_bp.route("/storage")
@admin_required
def storage_page():
    admin = get_current_admin()
    storage_data = get_admin_storage_breakdown(admin["id"])
    return render_template(
        "admin/storage.html",
        admin=admin,
        storage=storage_data,
        active_page="storage",
    )


@admin_bp.route("/profile")
@admin_required
def profile_page():
    admin = get_current_admin()
    session_security = {
        "role": admin.get("role"),
        "status": admin.get("status"),
        "last_login": admin.get("last_login"),
        "session_type": "Persistent" if session.permanent else "Browser session",
        "http_only": bool(current_app.config.get("SESSION_COOKIE_HTTPONLY", True)),
        "secure": bool(current_app.config.get("SESSION_COOKIE_SECURE", False)),
        "same_site": current_app.config.get("SESSION_COOKIE_SAMESITE") or "Lax",
    }
    return render_template("admin/profile.html", admin=admin, session_security=session_security, active_page="profile")


# ==============================================================================
# ADMIN REST API ENDPOINTS
# ==============================================================================

@api_admin_bp.after_request
def add_admin_api_no_cache_headers(response):
    """Ensure admin real-time telemetry APIs never return stale cached data."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@api_admin_bp.route("/stats", methods=["GET"])
@admin_required
def api_get_stats():
    admin = get_current_admin()
    try:
        stats = get_admin_dashboard_data(admin["id"])["stats"]
        return jsonify({"success": True, "stats": stats}), 200
    except Exception:
        current_app.logger.exception("Unable to load live Admin Dashboard stats")
        return jsonify({"success": False, "message": "Live MySQL dashboard data is temporarily unavailable."}), 503


@api_admin_bp.route("/dashboard-data", methods=["GET"])
@admin_required
def api_get_dashboard_data():
    admin = get_current_admin()
    try:
        return jsonify({"success": True, **get_admin_dashboard_data(admin["id"])}), 200
    except Exception:
        current_app.logger.exception("Unable to load live Admin Dashboard data")
        return jsonify({"success": False, "message": "Live MySQL dashboard data is temporarily unavailable."}), 503


@api_admin_bp.route("/notifications", methods=["GET"])
@admin_required
def api_get_notifications():
    admin = get_current_admin()
    limit = min(100, max(1, request.args.get("limit", default=50, type=int)))
    try:
        notifications = get_admin_notifications(admin["id"], limit=limit)
    except Exception:
        current_app.logger.exception("Unable to load live Admin Dashboard notifications")
        return jsonify({"success": False, "message": "Live MySQL notifications are temporarily unavailable."}), 503
    return jsonify({"success": True, "notifications": notifications}), 200


@api_admin_bp.route("/users", methods=["GET"])
@admin_required
def api_get_users():
    admin = get_current_admin()
    search = request.args.get("q")
    try:
        users = get_admin_managed_users(admin["id"], search_query=search)
    except Exception:
        current_app.logger.exception("Unable to load live MySQL users")
        return jsonify({"success": False, "message": "Live MySQL user data is temporarily unavailable."}), 503
    return jsonify({"success": True, "count": len(users), "users": users}), 200


@api_admin_bp.route("/users", methods=["POST"])
@admin_required
def api_create_user():
    admin = get_current_admin()
    payload = request.get_json(silent=True) or request.form.to_dict() or {}

    name = payload.get("name")
    email = payload.get("email")
    password = payload.get("password")
    confirm_password = payload.get("confirm_password")

    if not name or not email or not password:
        return jsonify({"success": False, "message": "Name, email, and password are required."}), 400

    if confirm_password and password != confirm_password:
        return jsonify({"success": False, "message": "Passwords do not match."}), 400

    user, error = create_user_by_admin(admin["id"], name, email, password)
    if user:
        return jsonify({"success": True, "message": f"User {user['name']} created successfully.", "user": user}), 201
    return jsonify({"success": False, "message": error or "Failed to create user."}), 400


@api_admin_bp.route("/users/<int:user_id>/status", methods=["POST", "PUT"])
@admin_required
def api_toggle_user_status(user_id):
    admin = get_current_admin()
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    new_status = payload.get("status")

    if not new_status:
        return jsonify({"success": False, "message": "New status is required ('active' or 'blocked')."}), 400

    success, message = update_user_status(user_id, new_status, admin["id"])
    if success:
        return jsonify({"success": True, "message": message, "status": new_status}), 200
    return jsonify({"success": False, "message": message}), 400


@api_admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@admin_required
def api_delete_user(user_id):
    admin = get_current_admin()
    success, message = delete_user_by_admin(user_id, admin["id"])
    if success:
        return jsonify({"success": True, "message": message}), 200
    return jsonify({"success": False, "message": message}), 400


@api_admin_bp.route("/documents", methods=["GET"])
@admin_required
def api_get_documents():
    admin = get_current_admin()
    search = request.args.get("q")
    doc_type = request.args.get("type")
    status = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    page = max(1, int(request.args.get("page", 1)))
    limit = min(100, max(1, int(request.args.get("limit", 20))))

    try:
        result = get_admin_documents(admin["id"], search=search, doc_type=doc_type, status=status, page=page, limit=limit, date_from=date_from, date_to=date_to)
    except Exception:
        current_app.logger.exception("Unable to load live MySQL documents")
        return jsonify({"success": False, "message": "Live MySQL document data is temporarily unavailable."}), 503
    return jsonify({"success": True, **result}), 200


@api_admin_bp.route("/documents/<string:job_id>", methods=["GET"])
@admin_required
def api_get_document_detail(job_id):
    admin = get_current_admin()
    try:
        detail = get_admin_document_detail(admin["id"], job_id)
    except Exception:
        current_app.logger.exception("Unable to load document detail")
        return jsonify({"success": False, "message": "Document details are temporarily unavailable."}), 503
    if not detail:
        return jsonify({"success": False, "message": "Document not found."}), 404
    return jsonify({"success": True, "document": detail}), 200


@api_admin_bp.route("/documents/<string:job_id>/preview", methods=["GET"])
@admin_required
def api_preview_document(job_id):
    admin = get_current_admin()
    try:
        detail = get_admin_document_detail(admin["id"], job_id)
    except Exception:
        current_app.logger.exception("Unable to load document preview")
        return jsonify({"success": False, "message": "Document preview is temporarily unavailable."}), 503
    filename = os.path.basename(detail.get("saved_file_name") or "") if detail else ""
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "")
    if not filename or not upload_folder or not os.path.isfile(os.path.join(upload_folder, filename)):
        return jsonify({"success": False, "message": "The original uploaded file is not available."}), 404
    return send_from_directory(upload_folder, filename, as_attachment=False)


@api_admin_bp.route("/documents/<string:job_id>", methods=["DELETE"])
@admin_required
def api_delete_document(job_id):
    admin = get_current_admin()
    success, message = delete_document_by_admin(job_id, admin["id"])
    if success:
        return jsonify({"success": True, "message": message}), 200
    return jsonify({"success": False, "message": message}), 400


@api_admin_bp.route("/analytics", methods=["GET"])
@admin_required
def api_get_analytics():
    admin = get_current_admin()
    try:
        snapshot = get_admin_dashboard_data(admin["id"])
    except Exception:
        current_app.logger.exception("Unable to load live MySQL analytics")
        return jsonify({"success": False, "message": "Live MySQL analytics are temporarily unavailable."}), 503
    data = {
        "volume_timeline": snapshot["analytics"]["upload_timeline"],
        "registration_timeline": snapshot["analytics"]["registration_timeline"],
        "type_distribution": snapshot["analytics"]["type_distribution"],
        "status_distribution": snapshot["analytics"]["status_distribution"],
        "user_activity_ranking": snapshot["analytics"]["user_activity"],
    }
    return jsonify({"success": True, "analytics": data}), 200


@api_admin_bp.route("/processing-monitor", methods=["GET"])
@admin_required
def api_get_processing_monitor():
    admin = get_current_admin()
    try:
        data = get_admin_processing_monitor(admin["id"])
    except Exception:
        current_app.logger.exception("Unable to load the live processing monitor")
        return jsonify({"success": False, "message": "Live processing data is temporarily unavailable."}), 503
    return jsonify({"success": True, "monitor": data}), 200


@api_admin_bp.route("/activity-logs", methods=["GET"])
@admin_required
def api_get_activity_logs():
    admin = get_current_admin()
    action = request.args.get("action")
    user_id = request.args.get("user_id")
    try:
        logs = get_admin_activity_logs(admin["id"], action_filter=action, user_id_filter=user_id, limit=200)
    except Exception:
        current_app.logger.exception("Unable to load live MySQL activity logs")
        return jsonify({"success": False, "message": "Live MySQL activity logs are temporarily unavailable."}), 503
    return jsonify({"success": True, "count": len(logs), "logs": logs}), 200


@api_admin_bp.route("/error-logs", methods=["GET"])
@admin_required
def api_get_error_logs():
    admin = get_current_admin()
    stage = request.args.get("stage")
    error_type = request.args.get("error_type")
    try:
        logs = get_admin_error_logs(admin["id"], stage_filter=stage, error_type_filter=error_type, limit=200)
    except Exception:
        current_app.logger.exception("Unable to load live MySQL error logs")
        return jsonify({"success": False, "message": "Live MySQL error logs are temporarily unavailable."}), 503
    return jsonify({"success": True, "count": len(logs), "logs": logs}), 200


@api_admin_bp.route("/storage", methods=["GET"])
@admin_required
def api_get_storage():
    admin = get_current_admin()
    try:
        data = get_admin_storage_breakdown(admin["id"])
    except Exception:
        current_app.logger.exception("Unable to load live MySQL-linked storage")
        return jsonify({"success": False, "message": "Live MySQL storage data is temporarily unavailable."}), 503
    return jsonify({"success": True, "storage": data}), 200


@api_admin_bp.route("/profile/password", methods=["POST"])
@admin_required
def api_change_password():
    admin = get_current_admin()
    payload = request.get_json(silent=True) or request.form.to_dict() or {}

    current_pw = payload.get("current_password")
    new_pw = payload.get("new_password")
    confirm_pw = payload.get("confirm_password")

    if not current_pw or not new_pw:
        return jsonify({"success": False, "message": "Current and new passwords are required."}), 400

    if confirm_pw and new_pw != confirm_pw:
        return jsonify({"success": False, "message": "New password and confirmation do not match."}), 400

    success, msg = update_user_password(admin["id"], current_pw, new_pw)
    if success:
        return jsonify({"success": True, "message": msg}), 200
    return jsonify({"success": False, "message": msg}), 400


@api_admin_bp.route("/profile", methods=["PATCH", "POST"])
@admin_required
def api_update_admin_profile():
    admin = get_current_admin()
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    name = payload.get("name")
    email = payload.get("email")
    if not name or not email:
        return jsonify({"success": False, "message": "Name and email are required."}), 400
    updated, error = update_admin_profile(admin["id"], name, email)
    if not updated:
        return jsonify({"success": False, "message": error or "Unable to update profile."}), 400
    return jsonify({"success": True, "message": "Administrator profile updated.", "admin": updated}), 200
