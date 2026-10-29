"""
Admin Operations & Analytics Service
Provides database-driven metrics, user management, document tracking, pipeline monitoring,
analytics, audit activity logs, error diagnostics, and storage statistics for administrators.
"""

import json
import importlib.util
import logging
import os
from contextlib import closing
from datetime import date, datetime, timedelta
from urllib.parse import quote

from config import Config
from services.database import get_active_db, get_db_connection, log_activity

logger = logging.getLogger(__name__)


def _admin_scope(admin_id, global_admin, alias, kind):
    if global_admin:
        return "1=1", []
    if kind == "user":
        return f"({alias}.admin_id = %s OR ({alias}.admin_id IS NULL AND {alias}.role = 'user') OR {alias}.id = %s)", [admin_id, admin_id]
    if kind == "activity":
        return f"({alias}.admin_id = %s OR {alias}.user_id = %s OR u.admin_id = %s OR {alias}.admin_id IS NULL)", [admin_id, admin_id, admin_id]
    return f"(u.admin_id = %s OR u.admin_id IS NULL OR {alias}.user_id = %s OR {alias}.user_id IS NULL)", [admin_id, admin_id]


def _iso_datetime(value, sentinel=False):
    if value is None or (sentinel and str(value).startswith("1000-01-01")):
        return None
    return value.isoformat(sep=" ", timespec="seconds") if isinstance(value, datetime) else str(value)


def _activity_actor_sql(cursor):
    """Return actor display expressions compatible with both activity-log table layouts."""
    cursor.execute("SHOW COLUMNS FROM `activity_logs`")
    columns = {row.get("Field") for row in cursor.fetchall()}
    has_actor_id = "actor_id" in columns
    has_actor_name = "actor_name" in columns
    has_actor_role = "actor_role" in columns
    actor_join = " LEFT JOIN users actor_user ON actor_user.id=a.actor_id" if has_actor_id else ""
    is_admin_actor = (
        "a.actor_role='admin'" if has_actor_role
        else "(a.action LIKE 'Admin %' OR (a.user_id IS NULL AND a.admin_id IS NOT NULL))"
    )
    fallback_name = f"CASE WHEN {is_admin_actor} THEN COALESCE(au.name,u.name) ELSE COALESCE(u.name,au.name) END"
    fallback_email = f"CASE WHEN {is_admin_actor} THEN COALESCE(au.email,u.email) ELSE COALESCE(u.email,au.email) END"
    actor_name = "COALESCE(NULLIF(a.actor_name,'')," if has_actor_name else "COALESCE("
    actor_email = "COALESCE(actor_user.email," if has_actor_id else "COALESCE("
    if has_actor_id:
        actor_name += "actor_user.name,"
    actor_name += fallback_name + ",'System') AS actor_name"
    actor_email += fallback_email + ",'') AS actor_email"
    return actor_join, actor_name, actor_email


def _admin_event_feed(cursor, admin_id, is_global, limit=50):
    """Build a seven-day event feed from persisted MySQL records without duplicating log/job events."""
    user_sql, user_params = _admin_scope(admin_id, is_global, "u", "user")
    doc_sql, doc_params = _admin_scope(admin_id, is_global, "d", "document")
    activity_sql, activity_params = _admin_scope(admin_id, is_global, "a", "activity")
    events = []

    cursor.execute(f"""
        SELECT u.id,u.name,u.email,u.created_at FROM users u
        WHERE {user_sql} AND u.role='user'
          AND u.created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
    """, user_params)
    for row in cursor.fetchall():
        events.append({
            "id": f"user:{row['id']}:registered", "event_type": "user",
            "action": "New user registered", "title": "New user registered",
            "details": f"{row.get('name') or row.get('email') or 'User'} created an account.",
            "actor_name": row.get("name") or "Unknown user", "actor_email": row.get("email") or "",
            "created_at": _iso_datetime(row.get("created_at")), "target_id": row["id"],
            "href": f"/admin/users?q={quote(row.get('email') or str(row['id']))}",
        })

    cursor.execute(f"""
        SELECT d.job_id,d.user_id,d.filename,d.status,d.current_stage,d.error_message,
               d.created_at,d.updated_at,
               CASE WHEN d.created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY) THEN 1 ELSE 0 END AS recent_upload,
               CASE WHEN d.updated_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY) THEN 1 ELSE 0 END AS recent_update,
               u.name AS actor_name,u.email AS actor_email
        FROM document_jobs d LEFT JOIN users u ON u.id=d.user_id
        WHERE {doc_sql}
          AND (d.created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
               OR d.updated_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY))
    """, doc_params)
    jobs = cursor.fetchall()

    # Error rows provide the failure's actual stage and message. They replace a second generic job alert.
    if is_global:
        error_sql, error_params = "1=1", []
    else:
        error_sql = "(e.admin_id=%s OR e.user_id=%s OR u.admin_id=%s OR e.admin_id IS NULL)"
        error_params = [admin_id, admin_id, admin_id]
    cursor.execute(f"""
        SELECT e.id,e.job_id,e.document_name,e.stage,e.error_type,e.error_message,e.created_at,
               e.user_id,u.name AS actor_name,u.email AS actor_email
        FROM error_logs e LEFT JOIN users u ON u.id=e.user_id
        WHERE {error_sql} AND e.created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
        ORDER BY e.created_at DESC
    """, error_params)
    error_rows = cursor.fetchall()
    error_jobs = {str(row.get("job_id")) for row in error_rows if row.get("job_id")}
    for row in error_rows:
        job_id = row.get("job_id")
        title = "Document processing failed" if job_id else "System error recorded"
        desc_parts = [part for part in (row.get("stage"), row.get("error_type"), row.get("error_message")) if part]
        events.append({
            "id": f"error:{row['id']}", "event_type": "error", "action": title, "title": title,
            "details": " · ".join(str(part) for part in desc_parts)[:500],
            "actor_name": row.get("actor_name") or "System", "actor_email": row.get("actor_email") or "",
            "created_at": _iso_datetime(row.get("created_at")), "target_id": job_id or row["id"],
            "href": f"/admin/documents?q={quote(str(job_id))}" if job_id else "/admin/error-logs",
        })

    final_statuses = {"completed", "complete", "processed", "success", "failed", "error"}
    for row in jobs:
        job_id = str(row.get("job_id") or "")
        filename = row.get("filename") or "Unspecified document"
        owner = row.get("actor_name") or "Unknown user"
        href = f"/admin/documents?q={quote(job_id)}"
        created_at = row.get("created_at")
        updated_at = row.get("updated_at")
        if created_at and row.get("recent_upload"):
            events.append({
                "id": f"job:{job_id}:uploaded", "event_type": "upload", "action": "Document uploaded",
                "title": "Document uploaded", "details": f"{filename} uploaded by {owner}.",
                "actor_name": owner, "actor_email": row.get("actor_email") or "",
                "created_at": _iso_datetime(created_at), "target_id": job_id, "href": href,
            })
        status = str(row.get("status") or "").strip().lower()
        if (status in final_statuses and row.get("recent_update") and updated_at and created_at and updated_at > created_at
                and job_id not in error_jobs):
            failed = status in ("failed", "error")
            title = "Document processing failed" if failed else "Document processing completed"
            detail = row.get("error_message") if failed else f"{filename} finished processing for {owner}."
            events.append({
                "id": f"job:{job_id}:{status}:{_iso_datetime(updated_at)}",
                "event_type": "error" if failed else "processing", "action": title, "title": title,
                "details": str(detail or "Processing failed.")[:500], "actor_name": owner,
                "actor_email": row.get("actor_email") or "", "created_at": _iso_datetime(updated_at),
                "target_id": job_id, "href": href,
            })

    actor_join, actor_name_sql, actor_email_sql = _activity_actor_sql(cursor)
    cursor.execute(f"""
        SELECT a.id,a.user_id,a.admin_id,a.action,a.details,a.created_at,
               {actor_name_sql},{actor_email_sql}
        FROM activity_logs a LEFT JOIN users u ON u.id=a.user_id
        LEFT JOIN users au ON au.id=a.admin_id
        {actor_join}
        WHERE {activity_sql} AND a.created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
        ORDER BY a.created_at DESC
    """, activity_params)
    mirrored_terms = ("register", "created user", "upload", "processing completed", "processed", "processing failed", "failed")
    important_terms = ("admin", "password", "deleted", "blocked", "activated", "profile", "system", "error")
    for row in cursor.fetchall():
        action = row.get("action") or "Activity"
        normalized = action.lower()
        if any(term in normalized for term in mirrored_terms):
            continue
        if not (row.get("admin_id") is not None or any(term in normalized for term in important_terms)):
            continue
        events.append({
            "id": f"activity:{row['id']}", "event_type": "system", "action": action, "title": action,
            "details": row.get("details") or "", "actor_name": row.get("actor_name") or "System",
            "actor_email": row.get("actor_email") or "", "created_at": _iso_datetime(row.get("created_at")),
            "target_id": row.get("user_id") or row.get("admin_id") or row["id"],
            "href": "/admin/activity-logs",
        })

    events.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return events[:max(1, min(int(limit or 50), 100))]


def get_admin_dashboard_data(admin_id):
    """Return a live, MySQL-only snapshot for the Admin Dashboard."""
    today = date.today()
    start_date = today - timedelta(days=6)
    days = [(start_date + timedelta(days=i)).isoformat() for i in range(7)]
    uploads = dict.fromkeys(days, 0)
    registrations = dict.fromkeys(days, 0)
    is_global = _is_global_admin(admin_id)
    user_sql, user_params = _admin_scope(admin_id, is_global, "u", "user")
    doc_sql, doc_params = _admin_scope(admin_id, is_global, "d", "document")
    activity_sql, activity_params = _admin_scope(admin_id, is_global, "a", "activity")
    result = {"stats": {}, "analytics": {}, "recent_users": [], "recent_documents": [], "recent_activity": [], "filters": {}}

    conn = get_db_connection()
    try:
        with closing(conn):
            with closing(conn.cursor(dictionary=True)) as cursor:
                cursor.execute("SELECT 1 AS connected")
                database_connected = bool(cursor.fetchone())
                cursor.execute(f"SELECT COUNT(*) AS total FROM users u WHERE {user_sql} AND u.role='user'", user_params)
                total_users = int(cursor.fetchone()["total"] or 0)

                cursor.execute(f"""
                    SELECT COUNT(*) AS total,
                           SUM(CASE WHEN LOWER(TRIM(COALESCE(d.status,''))) IN ('completed','complete','processed','success') THEN 1 ELSE 0 END) AS processed,
                           SUM(CASE WHEN LOWER(TRIM(COALESCE(d.status,''))) IN ('failed','error') THEN 1 ELSE 0 END) AS failed
                    FROM document_jobs d LEFT JOIN users u ON u.id = d.user_id WHERE {doc_sql}
                """, doc_params)
                totals = cursor.fetchone() or {}
                total_docs = int(totals.get("total") or 0)
                processed = int(totals.get("processed") or 0)
                failed = int(totals.get("failed") or 0)
                result["stats"] = {"total_users": total_users, "total_documents": total_docs,
                                    "processed_documents": processed, "failed_documents": failed,
                                    "pending_documents": max(0, total_docs - processed - failed)}

                cursor.execute(f"""
                    SELECT COALESCE(d.status, 'Unknown') AS status, COUNT(*) AS count
                    FROM document_jobs d LEFT JOIN users u ON u.id=d.user_id WHERE {doc_sql}
                      AND d.created_at >= %s AND d.created_at < %s
                    GROUP BY d.status ORDER BY count DESC
                """, doc_params + [start_date, today + timedelta(days=1)])
                status_distribution = {r["status"]: int(r["count"]) for r in cursor.fetchall()}
                cursor.execute(f"""
                    SELECT COALESCE(NULLIF(TRIM(d.document_type),''),'Unclassified') AS document_type, COUNT(*) AS count
                    FROM document_jobs d LEFT JOIN users u ON u.id=d.user_id WHERE {doc_sql}
                      AND d.created_at >= %s AND d.created_at < %s
                    GROUP BY document_type ORDER BY count DESC
                """, doc_params + [start_date, today + timedelta(days=1)])
                type_distribution = {r["document_type"]: int(r["count"]) for r in cursor.fetchall()}

                date_params = doc_params + [start_date, today + timedelta(days=1)]
                cursor.execute(f"""
                    SELECT DATE(d.created_at) AS day, COUNT(*) AS count FROM document_jobs d
                    LEFT JOIN users u ON u.id=d.user_id WHERE {doc_sql} AND d.created_at >= %s AND d.created_at < %s
                    GROUP BY DATE(d.created_at)
                """, date_params)
                for row in cursor.fetchall():
                    key = row["day"].isoformat() if row.get("day") else None
                    if key in uploads: uploads[key] = int(row["count"])
                cursor.execute(f"""
                    SELECT DATE(u.created_at) AS day, COUNT(*) AS count FROM users u
                    WHERE {user_sql} AND u.role='user' AND u.created_at >= %s AND u.created_at < %s GROUP BY DATE(u.created_at)
                """, user_params + [start_date, today + timedelta(days=1)])
                for row in cursor.fetchall():
                    key = row["day"].isoformat() if row.get("day") else None
                    if key in registrations: registrations[key] = int(row["count"])

                cursor.execute(f"""
                    SELECT u.id,u.name,u.email,u.status,u.created_at,u.last_login,
                           COUNT(DISTINCT d.job_id) AS document_count,
                           GREATEST(COALESCE(u.last_login,'1000-01-01 00:00:00'),
                                    COALESCE(MAX(d.created_at),'1000-01-01 00:00:00'),
                                    COALESCE(MAX(a.created_at),'1000-01-01 00:00:00')) AS last_activity
                    FROM users u LEFT JOIN document_jobs d ON d.user_id=u.id
                    LEFT JOIN activity_logs a ON a.user_id=u.id WHERE {user_sql} AND u.role='user'
                    GROUP BY u.id,u.name,u.email,u.status,u.created_at,u.last_login
                    ORDER BY u.created_at DESC LIMIT 8
                """, user_params)
                for row in cursor.fetchall():
                    for field in ("created_at", "last_login"):
                        row[field] = _iso_datetime(row.get(field))
                    row["last_activity"] = _iso_datetime(row.get("last_activity"), sentinel=True)
                    row["document_count"] = int(row.get("document_count") or 0)
                    result["recent_users"].append(row)

                cursor.execute(f"""
                    SELECT u.id,u.name,u.email,COUNT(DISTINCT d.job_id) AS count,MAX(d.created_at) AS last_upload
                    FROM users u LEFT JOIN document_jobs d ON d.user_id=u.id AND d.created_at >= %s
                    WHERE {user_sql} AND u.role='user'
                    GROUP BY u.id,u.name,u.email ORDER BY count DESC,u.created_at DESC LIMIT 8
                """, [start_date] + user_params)
                user_activity = [{"id":r["id"],"name":r["name"],"email":r["email"],"count":int(r["count"] or 0),"last_upload":_iso_datetime(r.get("last_upload"))} for r in cursor.fetchall()]

                cursor.execute(f"""
                    SELECT d.job_id,d.filename,d.document_type,d.confidence_score,d.processing_time,d.status,
                           d.current_stage,d.ocr_status,d.extraction_status,d.created_at,d.summary,d.error_message,
                           u.name AS user_name,u.email AS user_email
                    FROM document_jobs d LEFT JOIN users u ON u.id=d.user_id WHERE {doc_sql}
                    ORDER BY d.created_at DESC LIMIT 8
                """, doc_params)
                for row in cursor.fetchall():
                    row["created_at"] = _iso_datetime(row.get("created_at"))
                    result["recent_documents"].append(row)

                result["recent_activity"] = _admin_event_feed(cursor, admin_id, is_global, 12)

                cursor.execute(f"""SELECT DISTINCT d.status FROM document_jobs d
                    LEFT JOIN users u ON u.id=d.user_id WHERE {doc_sql}
                    AND d.created_at >= %s AND d.created_at < %s
                    AND d.status IS NOT NULL AND TRIM(d.status)<>'' ORDER BY d.status""", doc_params + [start_date, today + timedelta(days=1)])
                statuses = [r["status"] for r in cursor.fetchall()]
                cursor.execute(f"""SELECT DISTINCT d.document_type FROM document_jobs d
                    LEFT JOIN users u ON u.id=d.user_id WHERE {doc_sql}
                    AND d.created_at >= %s AND d.created_at < %s
                    AND d.document_type IS NOT NULL AND TRIM(d.document_type)<>'' ORDER BY d.document_type""", doc_params + [start_date, today + timedelta(days=1)])
                types = [r["document_type"] for r in cursor.fetchall()]

        ocr_ready = any(importlib.util.find_spec(module) for module in ("winocr", "paddleocr", "pytesseract"))
        result["analytics"] = {
            "upload_timeline": [{"date": day, "count": uploads[day]} for day in days],
            "registration_timeline": [{"date": day, "count": registrations[day]} for day in days],
            "status_distribution": status_distribution,
            "type_distribution": type_distribution,
            "user_activity": user_activity,
        }
        result["filters"] = {"statuses": statuses, "document_types": types}
        result["system_status"] = {"database": "online" if database_connected else "offline", "api": "online",
                                   "ocr": "configured" if ocr_ready else "unavailable",
                                   "last_sync": datetime.now().astimezone().isoformat(timespec="seconds")}
        return result
    finally:
        conn.close()


def _format_bytes(size_bytes):
    """Format bytes into readable KB/MB/GB strings."""
    if not size_bytes or size_bytes <= 0:
        return "0 KB"
    if size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{round(size_bytes / (1024 * 1024), 2)} MB"
    else:
        return f"{round(size_bytes / (1024 * 1024 * 1024), 2)} GB"


def _remove_job_files(job_id, saved_file_names=None):
    """Remove only the selected job's files while keeping all paths inside configured storage."""
    if not job_id:
        return 0
    root = os.path.realpath(Config.BASE_DIR)
    job_prefix = str(job_id).casefold()
    saved_names = {os.path.basename(str(name)).casefold() for name in (saved_file_names or []) if name}
    folders = {
        "Uploads": Config.UPLOAD_FOLDER,
        "Extracted JSON": Config.EXTRACTED_FOLDER,
        "Outputs": Config.OUTPUT_FOLDER,
    }
    removed = 0
    for label, folder in folders.items():
        folder_real = os.path.realpath(folder)
        if not os.path.isdir(folder_real) or os.path.commonpath([root, folder_real]) != root:
            continue
        for current, _, filenames in os.walk(folder_real):
            for filename in filenames:
                path = os.path.join(current, filename)
                try:
                    if os.path.islink(path):
                        continue
                    resolved = os.path.realpath(path)
                    if os.path.commonpath([folder_real, resolved]) != folder_real or os.path.commonpath([root, resolved]) != root:
                        continue
                    lowered = filename.casefold()
                    belongs = lowered in saved_names if label == "Uploads" else False
                    belongs = belongs or any(lowered.startswith(job_prefix + separator) for separator in (".", "_", "-"))
                    if belongs:
                        os.remove(path)
                        removed += 1
                except (OSError, ValueError) as exc:
                    logger.warning("Unable to remove linked %s artifact for job %s: %s", label, job_id, exc)
    return removed


def get_admin_notifications(admin_id, limit=50):
    """Return recent MySQL-backed registrations, document events, errors, and admin events."""
    is_global = _is_global_admin(admin_id)
    conn = get_db_connection()
    try:
        with closing(conn):
            with closing(conn.cursor(dictionary=True)) as cursor:
                return _admin_event_feed(cursor, admin_id, is_global, limit)
    finally:
        conn.close()


def _is_global_admin(admin_id):
    """
    Return True if this admin is a platform superadmin or global admin.
    - System Administrator (admin@docintel.io, id=23)
    - Primary admin (devanandpkamble1@gmail.com, id=1)
    - Any admin with name containing 'System' or 'Super'
    - Any admin with email in known platform admin emails
    - Any admin who has no specific tenant partition
    """
    if admin_id in (1, 23):
        return True
    try:
        conn = get_db_connection()
        with closing(conn):
            with closing(conn.cursor(dictionary=True)) as cur:
                cur.execute("SELECT id, name, email FROM users WHERE id = %s", (admin_id,))
                u = cur.fetchone()
                if not u:
                    return True
                email = (u.get("email") or "").lower()
                name = (u.get("name") or "").lower()
                if "system" in name or "super" in name or email in ("admin@docintel.io", "devanandpkamble1@gmail.com", "admin@intelligentocr.com"):
                    return True
                cur.execute("SELECT COUNT(*) as cnt FROM users WHERE admin_id = %s AND role = 'user'", (admin_id,))
                row = cur.fetchone()
                return (row["cnt"] if row else 0) == 0
    except Exception:
        return True


def get_admin_dashboard_stats(admin_id):
    """Compile overview metrics for the Admin Dashboard."""
    engine, conn = "mysql", get_db_connection()

    total_users = 0
    total_docs = 0
    processed_docs = 0
    failed_docs = 0
    processing_docs = 0
    total_extracted_data = 0
    storage_bytes = 0

    recent_users = []
    recent_docs = []
    recent_activity = []
    failed_jobs = []

    # Detect global/superadmin: if no users are directly assigned, show all data
    is_global = _is_global_admin(admin_id)

    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    # 1. Total users
                    if is_global:
                        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'user'")
                    else:
                        cursor.execute(
                            "SELECT COUNT(*) as count FROM users WHERE admin_id = %s OR (admin_id IS NULL AND role = 'user') OR id = %s",
                            (admin_id, admin_id)
                        )
                    row = cursor.fetchone()
                    total_users = row["count"] if row else 0

                    # 2. Document statistics
                    if is_global:
                        cursor.execute("""
                            SELECT
                                COUNT(job_id) as total_docs,
                                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as processed_docs,
                                SUM(CASE WHEN status = 'Failed' THEN 1 ELSE 0 END) as failed_docs,
                                SUM(CASE WHEN status IN ('Processing', 'Started', 'Pending', 'queued') THEN 1 ELSE 0 END) as processing_docs
                            FROM document_jobs
                        """)
                    else:
                        cursor.execute("""
                            SELECT
                                COUNT(d.job_id) as total_docs,
                                SUM(CASE WHEN d.status = 'Completed' THEN 1 ELSE 0 END) as processed_docs,
                                SUM(CASE WHEN d.status = 'Failed' THEN 1 ELSE 0 END) as failed_docs,
                                SUM(CASE WHEN d.status IN ('Processing', 'Started', 'Pending', 'queued') THEN 1 ELSE 0 END) as processing_docs
                            FROM document_jobs d
                            LEFT JOIN users u ON d.user_id = u.id
                            WHERE u.admin_id = %s OR u.admin_id IS NULL OR d.user_id = %s OR d.user_id IS NULL
                        """, (admin_id, admin_id))
                    doc_stats = cursor.fetchone() or {}
                    total_docs = doc_stats.get("total_docs") or 0
                    processed_docs = doc_stats.get("processed_docs") or 0
                    failed_docs = doc_stats.get("failed_docs") or 0
                    processing_docs = doc_stats.get("processing_docs") or 0

                    # 3. Recent users
                    if is_global:
                        cursor.execute("""
                            SELECT id, name, email, role, status, created_at, last_login
                            FROM users WHERE role = 'user'
                            ORDER BY created_at DESC LIMIT 5
                        """)
                    else:
                        cursor.execute("""
                            SELECT id, name, email, role, status, created_at, last_login
                            FROM users
                            WHERE admin_id = %s OR (admin_id IS NULL AND role = 'user') OR id = %s
                            ORDER BY created_at DESC LIMIT 5
                        """, (admin_id, admin_id))
                    for u in cursor.fetchall():
                        recent_users.append({
                            "id": u["id"],
                            "name": u["name"],
                            "email": u["email"],
                            "status": u.get("status") or "Unknown",
                            "created_at": u["created_at"].strftime("%Y-%m-%d %H:%M") if u.get("created_at") else "N/A",
                            "last_login": u["last_login"].strftime("%Y-%m-%d %H:%M") if u.get("last_login") else "Never"
                        })

                    # 4. Recent documents
                    if is_global:
                        cursor.execute("""
                            SELECT d.job_id, d.filename, d.document_type, d.confidence_score, d.processing_time, d.status, d.current_stage, d.created_at,
                                   u.name as user_name, u.email as user_email
                            FROM document_jobs d
                            LEFT JOIN users u ON d.user_id = u.id
                            ORDER BY d.created_at DESC LIMIT 6
                        """)
                    else:
                        cursor.execute("""
                            SELECT d.job_id, d.filename, d.document_type, d.confidence_score, d.processing_time, d.status, d.current_stage, d.created_at,
                                   u.name as user_name, u.email as user_email
                            FROM document_jobs d
                            LEFT JOIN users u ON d.user_id = u.id
                            WHERE u.admin_id = %s OR u.admin_id IS NULL OR d.user_id = %s OR d.user_id IS NULL
                            ORDER BY d.created_at DESC LIMIT 6
                        """, (admin_id, admin_id))
                    for d in cursor.fetchall():
                        recent_docs.append({
                            "job_id": d["job_id"],
                            "filename": d.get("filename", "Document"),
                            "document_type": d.get("document_type"),
                            "confidence_score": d.get("confidence_score"),
                            "processing_time": d.get("processing_time"),
                            "status": d.get("status"),
                            "current_stage": d.get("current_stage"),
                            "user_name": d.get("user_name") or "Unknown user",
                            "user_email": d.get("user_email") or "",
                            "created_at": d["created_at"].strftime("%Y-%m-%d %H:%M") if d.get("created_at") else "N/A"
                        })

                    # Recent activity shares the same real, seven-day event feed as notifications.
                    recent_activity.extend(_admin_event_feed(cursor, admin_id, is_global, 8))

                    # 6. Failed processing jobs
                    if is_global:
                        cursor.execute("""
                            SELECT d.job_id, d.filename, d.document_type, d.error_message, d.current_stage, d.created_at,
                                   u.name as user_name
                            FROM document_jobs d
                            LEFT JOIN users u ON d.user_id = u.id
                            WHERE d.status = 'Failed'
                            ORDER BY d.created_at DESC LIMIT 5
                        """)
                    else:
                        cursor.execute("""
                            SELECT d.job_id, d.filename, d.document_type, d.error_message, d.current_stage, d.created_at,
                                   u.name as user_name
                            FROM document_jobs d
                            LEFT JOIN users u ON d.user_id = u.id
                            WHERE (u.admin_id = %s OR u.admin_id IS NULL OR d.user_id = %s OR d.user_id IS NULL) AND d.status = 'Failed'
                            ORDER BY d.created_at DESC LIMIT 5
                        """, (admin_id, admin_id))
                    for f in cursor.fetchall():
                        failed_jobs.append({
                            "job_id": f["job_id"],
                            "filename": f.get("filename", "Document"),
                            "document_type": f.get("document_type"),
                            "error_message": f.get("error_message"),
                            "stage": f.get("current_stage"),
                            "user_name": f.get("user_name") or "Unknown user",
                            "created_at": f["created_at"].strftime("%Y-%m-%d %H:%M") if f.get("created_at") else "N/A"
                        })

                    # 7. Total extracted data fields
                    if is_global:
                        cursor.execute("SELECT data_json FROM document_jobs WHERE status = 'Completed'")
                    else:
                        cursor.execute("""
                            SELECT d.data_json FROM document_jobs d
                            LEFT JOIN users u ON d.user_id = u.id
                            WHERE (u.admin_id = %s OR u.admin_id IS NULL OR d.user_id = %s OR d.user_id IS NULL) AND d.status = 'Completed'
                        """, (admin_id, admin_id))
                    for r in cursor.fetchall():
                        try:
                            dj = json.loads(r.get("data_json") or "{}")
                            total_extracted_data += len(dj.get("extracted_fields") or dj.get("structured_data") or [])
                        except Exception:
                            pass
        else:
            with closing(conn):
                cursor = conn.cursor()
                if is_global:
                    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'user'")
                else:
                    cursor.execute("SELECT COUNT(*) as count FROM users WHERE admin_id = ? OR (admin_id IS NULL AND role = 'user') OR id = ?", (admin_id, admin_id))
                row = cursor.fetchone()
                total_users = row["count"] if row else 0

                if is_global:
                    cursor.execute("""
                        SELECT COUNT(job_id) as total_docs,
                               SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as processed_docs,
                               SUM(CASE WHEN status = 'Failed' THEN 1 ELSE 0 END) as failed_docs,
                               SUM(CASE WHEN status IN ('Processing', 'Started', 'Pending', 'queued') THEN 1 ELSE 0 END) as processing_docs
                        FROM document_jobs
                    """)
                else:
                    cursor.execute("""
                        SELECT COUNT(d.job_id) as total_docs,
                               SUM(CASE WHEN d.status = 'Completed' THEN 1 ELSE 0 END) as processed_docs,
                               SUM(CASE WHEN d.status = 'Failed' THEN 1 ELSE 0 END) as failed_docs,
                               SUM(CASE WHEN d.status IN ('Processing', 'Started', 'Pending', 'queued') THEN 1 ELSE 0 END) as processing_docs
                        FROM document_jobs d
                        LEFT JOIN users u ON d.user_id = u.id
                        WHERE u.admin_id = ? OR u.admin_id IS NULL OR d.user_id = ? OR d.user_id IS NULL
                    """, (admin_id, admin_id))
                doc_stats = dict(cursor.fetchone() or {})
                total_docs = doc_stats.get("total_docs") or 0
                processed_docs = doc_stats.get("processed_docs") or 0
                failed_docs = doc_stats.get("failed_docs") or 0
                processing_docs = doc_stats.get("processing_docs") or 0

                if is_global:
                    cursor.execute("""
                        SELECT id, name, email, role, status, created_at, last_login
                        FROM users WHERE role = 'user'
                        ORDER BY created_at DESC LIMIT 5
                    """)
                else:
                    cursor.execute("""
                        SELECT id, name, email, role, status, created_at, last_login
                        FROM users
                        WHERE admin_id = ? OR (admin_id IS NULL AND role = 'user') OR id = ?
                        ORDER BY created_at DESC LIMIT 5
                    """, (admin_id, admin_id))
                for u in cursor.fetchall():
                    u_dict = dict(u)
                    recent_users.append({
                        "id": u_dict["id"],
                        "name": u_dict["name"],
                        "email": u_dict["email"],
                        "status": u_dict.get("status") or "Unknown",
                        "created_at": str(u_dict.get("created_at", "N/A")),
                        "last_login": str(u_dict.get("last_login", "Never"))
                    })

                if is_global:
                    cursor.execute("""
                        SELECT d.job_id, d.filename, d.document_type, d.confidence_score, d.processing_time, d.status, d.current_stage, d.created_at,
                               u.name as user_name, u.email as user_email
                        FROM document_jobs d LEFT JOIN users u ON d.user_id = u.id
                        ORDER BY d.created_at DESC LIMIT 6
                    """)
                else:
                    cursor.execute("""
                        SELECT d.job_id, d.filename, d.document_type, d.confidence_score, d.processing_time, d.status, d.current_stage, d.created_at,
                               u.name as user_name, u.email as user_email
                        FROM document_jobs d LEFT JOIN users u ON d.user_id = u.id
                        WHERE u.admin_id = ? OR u.admin_id IS NULL OR d.user_id = ? OR d.user_id IS NULL
                        ORDER BY d.created_at DESC LIMIT 6
                    """, (admin_id, admin_id))
                for d in cursor.fetchall():
                    d_dict = dict(d)
                    recent_docs.append({
                        "job_id": d_dict["job_id"],
                        "filename": d_dict.get("filename", "Document"),
                        "document_type": d_dict.get("document_type"),
                        "confidence_score": d_dict.get("confidence_score"),
                        "processing_time": d_dict.get("processing_time"),
                        "status": d_dict.get("status"),
                        "current_stage": d_dict.get("current_stage"),
                        "user_name": d_dict.get("user_name") or "Unknown user",
                        "user_email": d_dict.get("user_email") or "",
                        "created_at": str(d_dict.get("created_at", "N/A"))
                    })

                if is_global:
                    cursor.execute("""
                        SELECT a.id, a.action, a.details, a.created_at, u.name as user_name
                        FROM activity_logs a LEFT JOIN users u ON a.user_id = u.id
                        ORDER BY a.created_at DESC LIMIT 8
                    """)
                else:
                    cursor.execute("""
                        SELECT a.id, a.action, a.details, a.created_at, u.name as user_name
                        FROM activity_logs a LEFT JOIN users u ON a.user_id = u.id
                        WHERE a.admin_id = ? OR a.user_id = ? OR u.admin_id = ? OR u.admin_id IS NULL OR a.admin_id IS NULL
                        ORDER BY a.created_at DESC LIMIT 8
                    """, (admin_id, admin_id, admin_id))
                for a in cursor.fetchall():
                    a_dict = dict(a)
                    recent_activity.append({
                        "id": a_dict["id"],
                        "action": a_dict["action"],
                        "details": a_dict.get("details", ""),
                        "user_name": a_dict.get("user_name") or "System",
                        "created_at": str(a_dict.get("created_at", "N/A"))
                    })

                if is_global:
                    cursor.execute("""
                        SELECT d.job_id, d.filename, d.document_type, d.error_message, d.current_stage, d.created_at, u.name as user_name
                        FROM document_jobs d LEFT JOIN users u ON d.user_id = u.id
                        WHERE d.status = 'Failed'
                        ORDER BY d.created_at DESC LIMIT 5
                    """)
                else:
                    cursor.execute("""
                        SELECT d.job_id, d.filename, d.document_type, d.error_message, d.current_stage, d.created_at, u.name as user_name
                        FROM document_jobs d LEFT JOIN users u ON d.user_id = u.id
                        WHERE (u.admin_id = ? OR u.admin_id IS NULL OR d.user_id = ? OR d.user_id IS NULL) AND d.status = 'Failed'
                        ORDER BY d.created_at DESC LIMIT 5
                    """, (admin_id, admin_id))
                    for f in cursor.fetchall():
                        f_dict = dict(f)
                        failed_jobs.append({
                            "job_id": f_dict["job_id"],
                            "filename": f_dict.get("filename", "Document"),
                            "document_type": f_dict.get("document_type"),
                            "error_message": f_dict.get("error_message"),
                            "stage": f_dict.get("current_stage"),
                            "user_name": f_dict.get("user_name") or "Unknown user",
                            "created_at": str(f_dict.get("created_at", "N/A"))
                        })

                    # 7. Total extracted data fields
                    if is_global:
                        cursor.execute("SELECT data_json FROM document_jobs WHERE status = 'Completed'")
                    else:
                        cursor.execute("""
                            SELECT d.data_json FROM document_jobs d
                            LEFT JOIN users u ON d.user_id = u.id
                            WHERE (u.admin_id = ? OR u.admin_id IS NULL OR d.user_id = ? OR d.user_id IS NULL) AND d.status = 'Completed'
                        """, (admin_id, admin_id))
                    for r in cursor.fetchall():
                        try:
                            dj = json.loads(dict(r).get("data_json") or "{}")
                            total_extracted_data += len(dj.get("extracted_fields") or dj.get("structured_data") or [])
                        except Exception:
                            pass
    except Exception as exc:
        logger.error("get_admin_dashboard_stats query error: %s", exc)

    # Count only files linked to live MySQL document records.
    try:
        storage_bytes = get_admin_storage_breakdown(admin_id)["total_bytes"]
    except Exception as exc:
        logger.warning("Unable to calculate database-linked storage: %s", exc)

    success_rate = round((processed_docs / max(1, (processed_docs + failed_docs))) * 100, 1) if (processed_docs + failed_docs) > 0 else (100.0 if total_docs > 0 else 0.0)

    return {
        "total_users": total_users,
        "total_documents": total_docs,
        "processed_documents": processed_docs,
        "failed_documents": failed_docs,
        "processing_documents": processing_docs,
        "total_extracted_data": total_extracted_data,
        "success_rate": f"{success_rate}%",
        "storage_used": _format_bytes(storage_bytes),
        "storage_bytes": storage_bytes,
        "recent_users": recent_users,
        "recent_documents": recent_docs,
        "recent_activity": recent_activity,
        "failed_jobs": failed_jobs
    }


def get_admin_documents(admin_id, search=None, doc_type=None, status=None, page=1, limit=50, date_from=None, date_to=None):
    """Retrieve documents belonging strictly to this admin's assigned users."""
    engine, conn = "mysql", get_db_connection()
    docs = []
    total_count = 0
    offset = (max(1, page) - 1) * limit

    search_pattern = f"%{search.strip()}%" if search else None

    is_global = _is_global_admin(admin_id)

    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    if is_global:
                        where_clauses = ["1=1"]
                        params = []
                    else:
                        where_clauses = ["(u.admin_id = %s OR u.admin_id IS NULL OR d.user_id = %s OR d.user_id IS NULL)"]
                        params = [admin_id, admin_id]

                    if search_pattern:
                        where_clauses.append("(d.filename LIKE %s OR d.document_type LIKE %s OR d.job_id LIKE %s OR u.name LIKE %s)")
                        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

                    if doc_type and doc_type.upper() != "ALL":
                        where_clauses.append("d.document_type LIKE %s")
                        params.append(f"%{doc_type}%")

                    if status and status.upper() != "ALL":
                        where_clauses.append("d.status = %s")
                        params.append(status)
                    if date_from:
                        where_clauses.append("d.created_at >= %s")
                        params.append(date_from)
                    if date_to:
                        where_clauses.append("d.created_at < DATE_ADD(%s, INTERVAL 1 DAY)")
                        params.append(date_to)

                    where_sql = " AND ".join(where_clauses)

                    count_query = f"""
                        SELECT COUNT(d.job_id) as total
                        FROM document_jobs d
                        LEFT JOIN users u ON d.user_id = u.id
                        WHERE {where_sql}
                    """
                    cursor.execute(count_query, params)
                    total_row = cursor.fetchone()
                    total_count = total_row["total"] if total_row else 0

                    data_query = f"""
                        SELECT d.job_id, d.filename, d.file_type, d.file_size, d.document_type,
                               d.confidence_score, d.processing_time, d.status, d.current_stage,
                               d.ocr_status, d.extraction_status,
                               d.summary, d.error_message, d.created_at,
                               u.id as user_id, u.name as user_name, u.email as user_email
                        FROM document_jobs d
                        LEFT JOIN users u ON d.user_id = u.id
                        WHERE {where_sql}
                        ORDER BY d.created_at DESC
                        LIMIT %s OFFSET %s
                    """
                    cursor.execute(data_query, params + [limit, offset])
                    for row in cursor.fetchall():
                        st = row.get("status") or "Unknown"
                        docs.append({
                            "job_id": row["job_id"],
                            "filename": row.get("filename", "Document"),
                            "file_type": row.get("file_type") or (row.get("filename", "").rsplit(".", 1)[-1].upper() if "." in row.get("filename", "") else "FILE"),
                            "file_size": row.get("file_size") or "N/A",
                            "document_type": row.get("document_type"),
                            "confidence_score": row.get("confidence_score"),
                            "processing_time": row.get("processing_time"),
                            "status": st,
                            "ocr_status": row.get("ocr_status"),
                            "extraction_status": row.get("extraction_status"),
                            "current_stage": row.get("current_stage"),
                            "error_message": row.get("error_message"),
                            "user_id": row.get("user_id"),
                            "user_name": row.get("user_name"),
                            "user_email": row.get("user_email"),
                            "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M") if row.get("created_at") else "N/A"
                        })
        else:
            with closing(conn):
                cursor = conn.cursor()
                if is_global:
                    where_clauses = ["1=1"]
                    params = []
                else:
                    where_clauses = ["(u.admin_id = ? OR u.admin_id IS NULL OR d.user_id = ? OR d.user_id IS NULL)"]
                    params = [admin_id, admin_id]

                if search_pattern:
                    where_clauses.append("(d.filename LIKE ? OR d.document_type LIKE ? OR d.job_id LIKE ? OR u.name LIKE ?)")
                    params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

                if doc_type and doc_type.upper() != "ALL":
                    where_clauses.append("d.document_type LIKE ?")
                    params.append(f"%{doc_type}%")

                if status and status.upper() != "ALL":
                    where_clauses.append("d.status = ?")
                    params.append(status)
                if date_from:
                    where_clauses.append("date(d.created_at) >= date(?)")
                    params.append(date_from)
                if date_to:
                    where_clauses.append("date(d.created_at) <= date(?)")
                    params.append(date_to)

                where_sql = " AND ".join(where_clauses)

                count_query = f"""
                    SELECT COUNT(d.job_id) as total
                    FROM document_jobs d
                    LEFT JOIN users u ON d.user_id = u.id
                    WHERE {where_sql}
                """
                cursor.execute(count_query, params)
                total_row = cursor.fetchone()
                total_count = total_row["total"] if total_row else 0

                data_query = f"""
                    SELECT d.job_id, d.filename, d.file_type, d.file_size, d.document_type,
                           d.confidence_score, d.processing_time, d.status, d.current_stage,
                           d.ocr_status, d.extraction_status,
                           d.summary, d.error_message, d.created_at,
                           u.id as user_id, u.name as user_name, u.email as user_email
                    FROM document_jobs d
                    LEFT JOIN users u ON d.user_id = u.id
                    WHERE {where_sql}
                    ORDER BY d.created_at DESC
                    LIMIT ? OFFSET ?
                """
                cursor.execute(data_query, params + [limit, offset])
                for r in cursor.fetchall():
                    row = dict(r)
                    st = row.get("status") or "Unknown"
                    docs.append({
                        "job_id": row["job_id"],
                        "filename": row.get("filename", "Document"),
                        "file_type": row.get("file_type") or (row.get("filename", "").rsplit(".", 1)[-1].upper() if "." in row.get("filename", "") else "FILE"),
                        "file_size": row.get("file_size") or "N/A",
                        "document_type": row.get("document_type"),
                        "confidence_score": row.get("confidence_score"),
                        "processing_time": row.get("processing_time"),
                        "status": st,
                        "ocr_status": row.get("ocr_status"),
                        "extraction_status": row.get("extraction_status"),
                        "current_stage": row.get("current_stage"),
                        "error_message": row.get("error_message"),
                        "user_id": row.get("user_id"),
                        "user_name": row.get("user_name"),
                        "user_email": row.get("user_email"),
                        "created_at": str(row.get("created_at", "N/A"))
                    })
    except Exception as exc:
        logger.error("get_admin_documents error: %s", exc)
        if engine == "mysql":
            raise

    return {
        "documents": docs,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total_count + limit - 1) // limit)
    }


def get_admin_document_detail(admin_id, job_id):
    """Fetch stored OCR and extraction output for one document visible to this admin."""
    is_global = _is_global_admin(admin_id)
    scope, params = _admin_scope(admin_id, is_global, "d", "document")
    conn = get_db_connection()
    try:
        with closing(conn):
            with closing(conn.cursor(dictionary=True)) as cursor:
                cursor.execute(f"""
                    SELECT d.job_id,d.user_id,d.filename,d.file_type,d.file_size,d.document_type,
                           d.confidence_score,d.processing_time,d.status,d.current_stage,d.ocr_status,
                           d.extraction_status,d.summary,d.error_message,d.data_json,d.created_at,
                           u.name AS user_name,u.email AS user_email
                    FROM document_jobs d LEFT JOIN users u ON u.id=d.user_id
                    WHERE d.job_id=%s AND {scope} LIMIT 1
                """, [job_id] + params)
                row = cursor.fetchone()
                if not row:
                    return None
                try:
                    payload = json.loads(row.get("data_json") or "{}")
                except (TypeError, ValueError):
                    payload = {}
                row.pop("data_json", None)
                row["created_at"] = _iso_datetime(row.get("created_at"))
                return {
                    **row,
                    "saved_file_name": payload.get("saved_file_name"),
                    "summary": payload.get("summary") or row.get("summary"),
                    "raw_text": payload.get("raw_text") or payload.get("ocr_text"),
                    "formatted_text": payload.get("formatted_text"),
                    "structured_data": payload.get("structured_data"),
                    "extracted_fields": payload.get("extracted_fields"),
                    "tables": payload.get("tables"),
                    "validation": payload.get("validation"),
                    "engine": payload.get("engine"),
                }
    finally:
        conn.close()


def get_admin_document_filter_options(admin_id):
    is_global = _is_global_admin(admin_id)
    scope, params = _admin_scope(admin_id, is_global, "d", "document")
    conn = get_db_connection()
    try:
        with closing(conn):
            with closing(conn.cursor(dictionary=True)) as cursor:
                cursor.execute(f"""
                    SELECT DISTINCT d.document_type FROM document_jobs d
                    LEFT JOIN users u ON u.id=d.user_id
                    WHERE {scope} AND d.document_type IS NOT NULL AND TRIM(d.document_type)<>''
                    ORDER BY d.document_type
                """, params)
                types = [r["document_type"] for r in cursor.fetchall()]
                cursor.execute(f"""
                    SELECT DISTINCT d.status FROM document_jobs d
                    LEFT JOIN users u ON u.id=d.user_id
                    WHERE {scope} AND d.status IS NOT NULL AND TRIM(d.status)<>''
                    ORDER BY d.status
                """, params)
                statuses = [r["status"] for r in cursor.fetchall()]
                return {"document_types": types, "statuses": statuses}
    finally:
        conn.close()


def delete_document_by_admin(job_id, admin_id):
    """Delete a document and its dependent MySQL rows/files without leaving broken references."""
    is_global = _is_global_admin(admin_id)
    engine, conn = "mysql", get_db_connection()
    saved_names = set()
    try:
        if engine == "mysql":
            doc_scope, scope_params = _admin_scope(admin_id, is_global, "d", "document")
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    cursor.execute(f"""
                        SELECT d.job_id,d.user_id,d.filename,d.data_json
                        FROM document_jobs d LEFT JOIN users u ON u.id=d.user_id
                        WHERE d.job_id=%s AND {doc_scope} LIMIT 1
                    """, [job_id] + scope_params)
                    job = cursor.fetchone()
                    if not job:
                        return False, "Document not found or unauthorized to delete."
                    try:
                        saved = json.loads(job.get("data_json") or "{}").get("saved_file_name")
                        if saved:
                            saved_names.add(str(saved))
                    except (TypeError, ValueError):
                        pass
                    cursor.execute("SELECT saved_file_name FROM documents WHERE job_id=%s", (job_id,))
                    saved_names.update(str(row["saved_file_name"]) for row in cursor.fetchall() if row.get("saved_file_name"))
                    cursor.execute("DELETE FROM error_logs WHERE job_id=%s", (job_id,))
                    cursor.execute("DELETE FROM documents WHERE job_id=%s", (job_id,))
                    cursor.execute("DELETE FROM document_jobs WHERE job_id=%s", (job_id,))
                    conn.commit()
            _remove_job_files(job_id, saved_names)
            log_activity("Admin deleted document", admin_id=admin_id,
                         details=f"Deleted document job {job_id} ({job.get('filename') or 'filename unavailable'})")
            return True, "Document and linked error records deleted successfully."

        with closing(conn):
            cursor = conn.cursor()
            if is_global:
                cursor.execute("SELECT job_id,user_id,filename,data_json FROM document_jobs WHERE job_id=? LIMIT 1", (job_id,))
            else:
                cursor.execute("""
                    SELECT d.job_id,d.user_id,d.filename,d.data_json FROM document_jobs d
                    LEFT JOIN users u ON d.user_id=u.id
                    WHERE d.job_id=? AND (u.admin_id=? OR u.admin_id IS NULL OR d.user_id IS NULL) LIMIT 1
                """, (job_id, admin_id))
            row = cursor.fetchone()
            job = dict(row) if row else None
            if not job:
                return False, "Document not found or unauthorized to delete."
            try:
                saved = json.loads(job.get("data_json") or "{}").get("saved_file_name")
                if saved:
                    saved_names.add(str(saved))
            except (TypeError, ValueError):
                pass
            cursor.execute("DELETE FROM error_logs WHERE job_id=?", (job_id,))
            cursor.execute("DELETE FROM document_jobs WHERE job_id=?", (job_id,))
            conn.commit()
        _remove_job_files(job_id, saved_names)
        log_activity("Admin deleted document", admin_id=admin_id, details=f"Deleted document job {job_id}")
        return True, "Document and linked error records deleted successfully."
    except Exception as exc:
        logger.error("delete_document_by_admin error: %s", exc)
        return False, str(exc)
    finally:
        conn.close()
def get_admin_analytics(admin_id):
    """Expose the same MySQL-backed, seven-day analytics used by the Admin Dashboard."""
    analytics = get_admin_dashboard_data(admin_id)["analytics"]
    return {
        "volume_timeline": analytics["upload_timeline"],
        "registration_timeline": analytics["registration_timeline"],
        "type_distribution": analytics["type_distribution"],
        "status_distribution": analytics["status_distribution"],
        "user_activity_ranking": analytics["user_activity"],
    }

def get_admin_processing_monitor(admin_id):
    """Retrieve stage-by-stage pipeline monitoring information."""
    STAGES = [
        "Upload",
        "File Validation",
        "OCR",
        "Text Extraction",
        "Document Classification",
        "Information Extraction",
        "JSON Generation",
        "Final Result"
    ]

    engine, conn = "mysql", get_db_connection()
    is_global = _is_global_admin(admin_id)
    doc_scope, doc_params = _admin_scope(admin_id, is_global, "d", "document")
    stage_counts = {s: 0 for s in STAGES}
    active_jobs = []
    recent_jobs = []

    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    # Current stage distribution
                    cursor.execute(f"""
                        SELECT d.current_stage, COUNT(d.job_id) as count
                        FROM document_jobs d
                        LEFT JOIN users u ON d.user_id = u.id
                        WHERE {doc_scope}
                        GROUP BY d.current_stage
                    """, doc_params)
                    for row in cursor.fetchall():
                        st = row.get("current_stage")
                        if st in stage_counts:
                            stage_counts[st] = row["count"]

                    # Active or recent jobs with stage indicators
                    cursor.execute(f"""
                        SELECT d.job_id, d.filename, d.document_type, d.status, d.current_stage,
                               d.confidence_score, d.processing_time, d.error_message, d.created_at,
                               u.name as user_name
                        FROM document_jobs d
                        LEFT JOIN users u ON d.user_id = u.id
                        WHERE {doc_scope}
                          AND (LOWER(COALESCE(d.status,'')) IN ('processing','pending','started','queued')
                               OR d.created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY))
                        ORDER BY d.created_at DESC LIMIT 15
                    """, doc_params)
                    for row in cursor.fetchall():
                        job_info = {
                            "job_id": row["job_id"],
                            "filename": row.get("filename"),
                            "document_type": row.get("document_type"),
                            "status": row.get("status"),
                            "current_stage": row.get("current_stage"),
                            "confidence_score": row.get("confidence_score"),
                            "processing_time": row.get("processing_time"),
                            "error_message": row.get("error_message"),
                            "user_name": row.get("user_name") or "Unknown user",
                            "created_at": _iso_datetime(row.get("created_at"))
                        }
                        if str(row.get("status") or "").lower() in ["processing", "pending", "started", "queued"]:
                            active_jobs.append(job_info)
                        else:
                            recent_jobs.append(job_info)
        else:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.current_stage, COUNT(d.job_id) as count
                    FROM document_jobs d
                    LEFT JOIN users u ON d.user_id = u.id
                    WHERE u.admin_id = ? OR u.admin_id IS NULL OR d.user_id = ? OR d.user_id IS NULL
                    GROUP BY d.current_stage
                """, (admin_id, admin_id))
                for row in cursor.fetchall():
                    r = dict(row)
                    st = r.get("current_stage")
                    if st in stage_counts:
                        stage_counts[st] = r["count"]

                cursor.execute("""
                    SELECT d.job_id, d.filename, d.document_type, d.status, d.current_stage,
                           d.confidence_score, d.processing_time, d.error_message, d.created_at,
                           u.name as user_name
                    FROM document_jobs d
                    LEFT JOIN users u ON d.user_id = u.id
                    WHERE u.admin_id = ? OR u.admin_id IS NULL OR d.user_id = ? OR d.user_id IS NULL
                    ORDER BY d.created_at DESC LIMIT 15
                """, (admin_id, admin_id))
                for row in cursor.fetchall():
                    r = dict(row)
                    job_info = {
                        "job_id": r["job_id"],
                        "filename": r.get("filename"),
                        "document_type": r.get("document_type"),
                        "status": r.get("status"),
                        "current_stage": r.get("current_stage"),
                        "confidence_score": r.get("confidence_score"),
                        "processing_time": r.get("processing_time"),
                        "error_message": r.get("error_message"),
                        "user_name": r.get("user_name") or "Unknown user",
                        "created_at": str(r.get("created_at", "N/A"))
                    }
                    if str(r.get("status") or "").lower() in ["processing", "pending", "started", "queued"]:
                        active_jobs.append(job_info)
                    else:
                        recent_jobs.append(job_info)
    except Exception as exc:
        logger.error("get_admin_processing_monitor error: %s", exc)
        if engine == "mysql":
            raise

    return {
        "pipeline_stages": STAGES,
        "stage_counts": stage_counts,
        "active_jobs": active_jobs,
        "recent_jobs": recent_jobs
    }


def get_admin_activity_logs(admin_id, action_filter=None, user_id_filter=None, limit=100):
    """Retrieve audit activity logs for this admin and managed users."""
    engine, conn = "mysql", get_db_connection()
    logs = []

    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    actor_join, actor_name_sql, actor_email_sql = _activity_actor_sql(cursor)
                    where_clauses = ["(a.admin_id = %s OR a.user_id = %s OR u.admin_id = %s OR a.admin_id IS NULL)",
                                     "a.created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)"]
                    params = [admin_id, admin_id, admin_id]

                    if action_filter and action_filter.upper() != "ALL":
                        where_clauses.append("a.action LIKE %s")
                        params.append(f"%{action_filter}%")

                    if user_id_filter:
                        where_clauses.append("a.user_id = %s")
                        params.append(user_id_filter)

                    where_sql = " AND ".join(where_clauses)
                    query = f"""
                        SELECT a.id, a.user_id, a.admin_id, a.action, a.details, a.ip_address, a.created_at,
                               {actor_name_sql.replace('AS actor_name', 'AS user_name')},
                               {actor_email_sql.replace('AS actor_email', 'AS user_email')}
                        FROM activity_logs a
                        LEFT JOIN users u ON a.user_id = u.id
                        LEFT JOIN users au ON au.id=a.admin_id
                        {actor_join}
                        WHERE {where_sql}
                        ORDER BY a.created_at DESC
                        LIMIT %s
                    """
                    cursor.execute(query, params + [limit])
                    for row in cursor.fetchall():
                        logs.append({
                            "id": row["id"],
                            "action": row["action"],
                            "details": row.get("details") or "",
                            "ip_address": row.get("ip_address") or "Unavailable",
                            "user_name": row.get("user_name") or "Unknown actor",
                            "user_email": row.get("user_email") or "",
                            "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("created_at") else "N/A"
                        })
        else:
            with closing(conn):
                cursor = conn.cursor()
                where_clauses = ["(a.admin_id = ? OR a.user_id = ? OR u.admin_id = ? OR a.admin_id IS NULL)",
                                 "date(a.created_at) >= date('now','-6 days')"]
                params = [admin_id, admin_id, admin_id]

                if action_filter and action_filter.upper() != "ALL":
                    where_clauses.append("a.action LIKE ?")
                    params.append(f"%{action_filter}%")

                if user_id_filter:
                    where_clauses.append("a.user_id = ?")
                    params.append(user_id_filter)

                where_sql = " AND ".join(where_clauses)
                query = f"""
                    SELECT a.id, a.user_id, a.admin_id, a.action, a.details, a.ip_address, a.created_at,
                           u.name as user_name, u.email as user_email
                    FROM activity_logs a
                    LEFT JOIN users u ON a.user_id = u.id
                    WHERE {where_sql}
                    ORDER BY a.created_at DESC
                    LIMIT ?
                """
                cursor.execute(query, params + [limit])
                for row in cursor.fetchall():
                    r = dict(row)
                    logs.append({
                        "id": r["id"],
                        "action": r["action"],
                        "details": r.get("details") or "",
                        "ip_address": r.get("ip_address") or "Unavailable",
                        "user_name": r.get("user_name") or "Unknown actor",
                        "user_email": r.get("user_email") or "",
                        "created_at": str(r.get("created_at", "N/A"))
                    })
    except Exception as exc:
        logger.error("get_admin_activity_logs error: %s", exc)
        if engine == "mysql":
            raise

    return logs


def get_admin_error_logs(admin_id, stage_filter=None, error_type_filter=None, limit=100):
    """Retrieve error diagnostic logs for OCR/AI extraction failures."""
    engine, conn = "mysql", get_db_connection()
    logs = []

    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    where_clauses = ["(e.admin_id = %s OR e.user_id = %s OR u.admin_id = %s OR e.admin_id IS NULL)",
                                     "e.created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)"]
                    params = [admin_id, admin_id, admin_id]

                    if stage_filter and stage_filter.upper() != "ALL":
                        where_clauses.append("e.stage = %s")
                        params.append(stage_filter)

                    if error_type_filter and error_type_filter.upper() != "ALL":
                        where_clauses.append("e.error_type = %s")
                        params.append(error_type_filter)

                    where_sql = " AND ".join(where_clauses)
                    query = f"""
                        SELECT e.id, e.job_id, e.document_name, e.stage, e.error_type, e.error_message, e.stack_trace, e.created_at,
                               u.name as user_name, u.email as user_email
                        FROM error_logs e
                        LEFT JOIN users u ON e.user_id = u.id
                        WHERE {where_sql}
                        ORDER BY e.created_at DESC
                        LIMIT %s
                    """
                    cursor.execute(query, params + [limit])
                    for row in cursor.fetchall():
                        logs.append({
                            "id": row["id"],
                            "job_id": row.get("job_id") or "N/A",
                            "document_name": row.get("document_name") or "Unspecified document",
                            "stage": row["stage"],
                            "error_type": row["error_type"],
                            "error_message": row["error_message"],
                            "stack_trace": row.get("stack_trace"),
                            "user_name": row.get("user_name") or "System",
                            "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("created_at") else "N/A"
                        })
        else:
            with closing(conn):
                cursor = conn.cursor()
                where_clauses = ["(e.admin_id = ? OR e.user_id = ? OR u.admin_id = ? OR e.admin_id IS NULL)",
                                 "date(e.created_at) >= date('now','-6 days')"]
                params = [admin_id, admin_id, admin_id]

                if stage_filter and stage_filter.upper() != "ALL":
                    where_clauses.append("e.stage = ?")
                    params.append(stage_filter)

                if error_type_filter and error_type_filter.upper() != "ALL":
                    where_clauses.append("e.error_type = ?")
                    params.append(error_type_filter)

                where_sql = " AND ".join(where_clauses)
                query = f"""
                    SELECT e.id, e.job_id, e.document_name, e.stage, e.error_type, e.error_message, e.stack_trace, e.created_at,
                           u.name as user_name, u.email as user_email
                    FROM error_logs e
                    LEFT JOIN users u ON e.user_id = u.id
                    WHERE {where_sql}
                    ORDER BY e.created_at DESC
                    LIMIT ?
                """
                cursor.execute(query, params + [limit])
                for row in cursor.fetchall():
                    r = dict(row)
                    logs.append({
                        "id": r["id"],
                        "job_id": r.get("job_id") or "N/A",
                        "document_name": r.get("document_name") or "Unspecified document",
                        "stage": r["stage"],
                        "error_type": r["error_type"],
                        "error_message": r["error_message"],
                        "stack_trace": r.get("stack_trace"),
                        "user_name": r.get("user_name") or "System",
                        "created_at": str(r.get("created_at", "N/A"))
                    })
    except Exception as exc:
        logger.error("get_admin_error_logs error: %s", exc)
        if engine == "mysql":
            raise

    return logs


def get_admin_storage_breakdown(admin_id):
    """Report physical files referenced by current MySQL document records only."""
    folders = {
        "Uploads": Config.UPLOAD_FOLDER,
        "Extracted JSON": Config.EXTRACTED_FOLDER,
        "Outputs": Config.OUTPUT_FOLDER,
    }
    is_global = _is_global_admin(admin_id)
    doc_sql, doc_params = _admin_scope(admin_id, is_global, "d", "document")
    jobs = {}
    upload_names = set()
    upload_job_ids = {}
    conn = get_db_connection()
    try:
        with closing(conn):
            with closing(conn.cursor(dictionary=True)) as cursor:
                cursor.execute(f"""
                    SELECT d.job_id,d.user_id,d.filename,d.data_json,u.name AS owner_name
                    FROM document_jobs d LEFT JOIN users u ON u.id=d.user_id
                    WHERE {doc_sql}
                """, doc_params)
                for row in cursor.fetchall():
                    job_id = str(row.get("job_id") or "")
                    if not job_id:
                        continue
                    try:
                        payload = json.loads(row.get("data_json") or "{}")
                    except (TypeError, ValueError):
                        payload = {}
                    saved = payload.get("saved_file_name")
                    if saved:
                        saved_key = os.path.basename(str(saved)).casefold()
                        upload_names.add(saved_key)
                        upload_job_ids[saved_key] = job_id.casefold()
                    jobs[job_id.casefold()] = {
                        "job_id": job_id,
                        "filename": row.get("filename"),
                        "owner": row.get("owner_name"),
                    }

                # The legacy documents table remains part of the live MySQL schema. Use it only
                # for jobs absent from document_jobs so the same document is never counted twice.
                cursor.execute(f"""
                    SELECT d.job_id,d.user_id,d.filename,d.saved_file_name,u.name AS owner_name
                    FROM documents d LEFT JOIN users u ON u.id=d.user_id
                    WHERE {doc_sql}
                """, doc_params)
                for row in cursor.fetchall():
                    job_id = str(row.get("job_id") or "")
                    key = job_id.casefold()
                    if row.get("saved_file_name"):
                        saved_key = os.path.basename(str(row["saved_file_name"])).casefold()
                        upload_names.add(saved_key)
                        upload_job_ids[saved_key] = key
                    if job_id and key not in jobs:
                        jobs[key] = {"job_id": job_id, "filename": row.get("filename"), "owner": row.get("owner_name")}
    finally:
        conn.close()

    folder_stats = {}
    extension_totals = {}
    physical_paths = set()
    total_bytes = 0
    total_files = 0
    unlinked_files = 0
    unlinked_bytes = 0
    top_files = []

    def referenced(label, filename):
        if label == "Uploads":
            return filename.casefold() in upload_names
        lowered = filename.casefold()
        return any(lowered.startswith(job_id + separator) for job_id in jobs for separator in (".", "_", "-"))

    for label, folder in folders.items():
        folder_bytes = 0
        folder_count = 0
        if os.path.isdir(folder):
            for root, _, filenames in os.walk(folder):
                for filename in filenames:
                    path = os.path.join(root, filename)
                    try:
                        if not os.path.isfile(path):
                            continue
                        physical_path = os.path.normcase(os.path.realpath(path))
                        size = os.path.getsize(path)
                    except OSError:
                        continue
                    if physical_path in physical_paths:
                        continue
                    physical_paths.add(physical_path)
                    if not referenced(label, filename):
                        unlinked_files += 1
                        unlinked_bytes += size
                        continue

                    folder_count += 1
                    folder_bytes += size
                    total_files += 1
                    total_bytes += size
                    extension = filename.rsplit(".", 1)[-1].upper() if "." in filename else "OTHER"
                    entry = extension_totals.setdefault(extension, {"size": 0, "count": 0})
                    entry["size"] += size
                    entry["count"] += 1
                    lowered = filename.casefold()
                    job = next((jobs[key] for key in sorted(jobs, key=len, reverse=True)
                                if any(lowered.startswith(key + separator) for separator in (".", "_", "-"))), None)
                    if label == "Uploads":
                        job = jobs.get(upload_job_ids.get(filename.casefold(), ""), job)
                    top_files.append({
                        "name": filename,
                        "folder": label,
                        "size": size,
                        "formatted_size": _format_bytes(size),
                        "job_id": job.get("job_id") if job else None,
                        "owner": job.get("owner") if job else None,
                    })
        folder_stats[label] = {
            "size": folder_bytes,
            "formatted_size": _format_bytes(folder_bytes),
            "file_count": folder_count,
        }

    top_files.sort(key=lambda item: item["size"], reverse=True)
    extension_breakdown = {
        extension: {**values, "formatted_size": _format_bytes(values["size"])}
        for extension, values in sorted(extension_totals.items())
    }
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    return {
        "total_storage": _format_bytes(total_bytes),
        "total_bytes": total_bytes,
        "total_files": total_files,
        "database_documents": len(jobs),
        "unlinked_files": unlinked_files,
        "unlinked_bytes": unlinked_bytes,
        "folder_stats": folder_stats,
        "extension_breakdown": extension_breakdown,
        "top_files": top_files[:10],
        "last_sync": now,
    }
