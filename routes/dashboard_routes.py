"""
User Dashboard API Routes
Provides database-driven metrics, volume timelines, document classifications,
confidence tracking, and recent uploads strictly for authenticated users.
Zero hardcoded, placeholder, or randomly generated statistics.
"""

from contextlib import closing
from datetime import datetime, timedelta
import logging
from flask import jsonify, request, session
from services.database import get_active_db
from . import api_bp, api_v1_bp

logger = logging.getLogger(__name__)


def _get_current_user_id():
    """Extract authenticated user ID from server-side Flask session."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        return int(user_id)
    except (ValueError, TypeError):
        return None


def _parse_confidence_value(raw_val):
    """Cleanly parse confidence percentage or float into a 0.0 - 100.0 float."""
    if raw_val is None:
        return 0.0
    try:
        val_str = str(raw_val).rstrip('%').strip()
        f = float(val_str)
        if 0 < f <= 1.0:
            f = f * 100.0
        return round(f, 1)
    except Exception:
        return 0.0


# ==============================================================================
# 1. GET /api/dashboard/stats
# ==============================================================================
@api_bp.route("/dashboard/stats", methods=["GET"])
@api_v1_bp.route("/dashboard/stats", methods=["GET"])
def get_user_dashboard_stats():
    """Return top metric card counters strictly from database records."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    engine, conn = get_active_db()
    total_docs = 0
    processed_docs = 0
    processing_docs = 0
    failed_docs = 0

    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    cursor.execute("""
                        SELECT 
                            COUNT(job_id) as total_docs,
                            SUM(CASE WHEN status IN ('Completed', 'completed', 'success', 'Success') THEN 1 ELSE 0 END) as processed_docs,
                            SUM(CASE WHEN status IN ('Processing', 'processing', 'Started', 'started', 'Pending', 'pending', 'queued', 'Queued') THEN 1 ELSE 0 END) as processing_docs,
                            SUM(CASE WHEN status IN ('Failed', 'failed', 'Error', 'error') THEN 1 ELSE 0 END) as failed_docs
                        FROM document_jobs
                        WHERE user_id = %s
                    """, (user_id,))
                    row = cursor.fetchone() or {}
                    total_docs = int(row.get("total_docs") or 0)
                    processed_docs = int(row.get("processed_docs") or 0)
                    processing_docs = int(row.get("processing_docs") or 0)
                    failed_docs = int(row.get("failed_docs") or 0)
        else:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        COUNT(job_id) as total_docs,
                        SUM(CASE WHEN status IN ('Completed', 'completed', 'success', 'Success') THEN 1 ELSE 0 END) as processed_docs,
                        SUM(CASE WHEN status IN ('Processing', 'processing', 'Started', 'started', 'Pending', 'pending', 'queued', 'Queued') THEN 1 ELSE 0 END) as processing_docs,
                        SUM(CASE WHEN status IN ('Failed', 'failed', 'Error', 'error') THEN 1 ELSE 0 END) as failed_docs
                    FROM document_jobs
                    WHERE user_id = ?
                """, (user_id,))
                row = dict(cursor.fetchone() or {})
                total_docs = int(row.get("total_docs") or 0)
                processed_docs = int(row.get("processed_docs") or 0)
                processing_docs = int(row.get("processing_docs") or 0)
                failed_docs = int(row.get("failed_docs") or 0)
    except Exception as exc:
        logger.error("get_user_dashboard_stats DB error for user %s: %s", user_id, exc)
        return jsonify({"success": False, "message": "Failed to query database statistics."}), 500

    return jsonify({
        "success": True,
        "total_documents": total_docs,
        "processed": processed_docs,
        "processing": processing_docs,
        "failed": failed_docs
    }), 200


# ==============================================================================
# 2. GET /api/dashboard/upload-activity
# ==============================================================================
@api_bp.route("/dashboard/upload-activity", methods=["GET"])
@api_v1_bp.route("/dashboard/upload-activity", methods=["GET"])
def get_user_upload_activity():
    """Return upload volume grouped strictly by date without duplicates."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    period = request.args.get("period", "30").strip().lower()
    days_map = {"7": 7, "30": 30, "90": 90}
    days = days_map.get(period)

    engine, conn = get_active_db()
    timeline_records = []

    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    if days:
                        cursor.execute("""
                            SELECT DATE(created_at) as date_val, COUNT(job_id) as doc_count
                            FROM document_jobs
                            WHERE user_id = %s AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                            GROUP BY DATE(created_at)
                            ORDER BY date_val ASC
                        """, (user_id, days))
                    else:
                        cursor.execute("""
                            SELECT DATE(created_at) as date_val, COUNT(job_id) as doc_count
                            FROM document_jobs
                            WHERE user_id = %s
                            GROUP BY DATE(created_at)
                            ORDER BY date_val ASC
                        """, (user_id,))
                    for row in cursor.fetchall():
                        d_val = row.get("date_val")
                        if d_val:
                            timeline_records.append({
                                "date": d_val.strftime("%Y-%m-%d") if hasattr(d_val, "strftime") else str(d_val),
                                "label": d_val.strftime("%b %d, %Y") if hasattr(d_val, "strftime") else str(d_val),
                                "count": int(row.get("doc_count") or 0)
                            })
        else:
            with closing(conn):
                cursor = conn.cursor()
                if days:
                    cursor.execute("""
                        SELECT DATE(created_at) as date_val, COUNT(job_id) as doc_count
                        FROM document_jobs
                        WHERE user_id = ? AND created_at >= datetime('now', ? || ' days')
                        GROUP BY DATE(created_at)
                        ORDER BY date_val ASC
                    """, (user_id, f"-{days}"))
                else:
                    cursor.execute("""
                        SELECT DATE(created_at) as date_val, COUNT(job_id) as doc_count
                        FROM document_jobs
                        WHERE user_id = ?
                        GROUP BY DATE(created_at)
                        ORDER BY date_val ASC
                    """, (user_id,))
                for r in cursor.fetchall():
                    row = dict(r)
                    raw_d = str(row.get("date_val", ""))
                    label = raw_d
                    try:
                        dt = datetime.strptime(raw_d, "%Y-%m-%d")
                        label = dt.strftime("%b %d, %Y")
                    except Exception:
                        pass
                    timeline_records.append({
                        "date": raw_d,
                        "label": label,
                        "count": int(row.get("doc_count") or 0)
                    })
    except Exception as exc:
        logger.error("get_user_upload_activity DB error for user %s: %s", user_id, exc)
        return jsonify({"success": False, "message": "Failed to query upload activity."}), 500

    labels = [r["label"] for r in timeline_records]
    raw_dates = [r["date"] for r in timeline_records]
    counts = [r["count"] for r in timeline_records]
    total_in_period = sum(counts)

    return jsonify({
        "success": True,
        "period": period,
        "labels": labels,
        "dates": raw_dates,
        "counts": counts,
        "total": total_in_period,
        "empty": len(labels) == 0
    }), 200


# ==============================================================================
# 3. GET /api/dashboard/document-types
# ==============================================================================
@api_bp.route("/dashboard/document-types", methods=["GET"])
@api_v1_bp.route("/dashboard/document-types", methods=["GET"])
def get_user_document_types():
    """Return real distribution of classified document types for this user."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    engine, conn = get_active_db()
    types_list = []

    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    cursor.execute("""
                        SELECT document_type, COUNT(job_id) as type_count
                        FROM document_jobs
                        WHERE user_id = %s
                        GROUP BY document_type
                        ORDER BY type_count DESC
                    """, (user_id,))
                    for row in cursor.fetchall():
                        doc_type = row.get("document_type") or "General Document"
                        types_list.append({
                            "type": doc_type,
                            "count": int(row.get("type_count") or 0)
                        })
        else:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT document_type, COUNT(job_id) as type_count
                    FROM document_jobs
                    WHERE user_id = ?
                    GROUP BY document_type
                    ORDER BY type_count DESC
                """, (user_id,))
                for r in cursor.fetchall():
                    row = dict(r)
                    doc_type = row.get("document_type") or "General Document"
                    types_list.append({
                        "type": doc_type,
                        "count": int(row.get("type_count") or 0)
                    })
    except Exception as exc:
        logger.error("get_user_document_types DB error for user %s: %s", user_id, exc)
        return jsonify({"success": False, "message": "Failed to query document types."}), 500

    labels = [item["type"] for item in types_list]
    counts = [item["count"] for item in types_list]
    total_docs = sum(counts)

    return jsonify({
        "success": True,
        "labels": labels,
        "counts": counts,
        "types": types_list,
        "total": total_docs,
        "empty": len(labels) == 0
    }), 200


# ==============================================================================
# 4. GET /api/dashboard/confidence
# ==============================================================================
@api_bp.route("/dashboard/confidence", methods=["GET"])
@api_v1_bp.route("/dashboard/confidence", methods=["GET"])
def get_user_confidence_analytics():
    """Return real confidence scores for processed documents strictly from DB."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    engine, conn = get_active_db()
    items = []

    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    cursor.execute("""
                        SELECT job_id, filename, document_type, confidence_score, created_at
                        FROM document_jobs
                        WHERE user_id = %s AND status IN ('Completed', 'completed', 'success', 'Success')
                        ORDER BY created_at ASC
                        LIMIT 30
                    """, (user_id,))
                    for row in cursor.fetchall():
                        created = row.get("created_at")
                        date_str = created.strftime("%b %d") if hasattr(created, "strftime") else "N/A"
                        items.append({
                            "job_id": row["job_id"],
                            "filename": row.get("filename") or "Document",
                            "document_type": row.get("document_type") or "General Document",
                            "confidence": _parse_confidence_value(row.get("confidence_score")),
                            "confidence_display": str(row.get("confidence_score") or "0%"),
                            "date": date_str
                        })
        else:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT job_id, filename, document_type, confidence_score, created_at
                    FROM document_jobs
                    WHERE user_id = ? AND status IN ('Completed', 'completed', 'success', 'Success')
                    ORDER BY created_at ASC
                    LIMIT 30
                """, (user_id,))
                for r in cursor.fetchall():
                    row = dict(r)
                    created = row.get("created_at")
                    date_str = str(created)[:10] if created else "N/A"
                    try:
                        dt = datetime.strptime(str(created)[:19], "%Y-%m-%d %H:%M:%S")
                        date_str = dt.strftime("%b %d")
                    except Exception:
                        pass
                    items.append({
                        "job_id": row["job_id"],
                        "filename": row.get("filename") or "Document",
                        "document_type": row.get("document_type") or "General Document",
                        "confidence": _parse_confidence_value(row.get("confidence_score")),
                        "confidence_display": str(row.get("confidence_score") or "0%"),
                        "date": date_str
                    })
    except Exception as exc:
        logger.error("get_user_confidence_analytics DB error for user %s: %s", user_id, exc)
        return jsonify({"success": False, "message": "Failed to query confidence analytics."}), 500

    labels = [f"Doc {idx}" for idx in range(1, len(items) + 1)]
    values = [item["confidence"] for item in items]
    filenames = [item["filename"] for item in items]
    job_ids = [item["job_id"] for item in items]
    doc_types = [item["document_type"] for item in items]
    avg_conf = round(sum(values) / len(values), 1) if values else 0.0

    return jsonify({
        "success": True,
        "labels": labels,
        "values": values,
        "filenames": filenames,
        "job_ids": job_ids,
        "document_types": doc_types,
        "average": avg_conf,
        "count": len(items),
        "empty": len(items) == 0
    }), 200


# ==============================================================================
# 5. GET /api/dashboard/recent-documents
# ==============================================================================
@api_bp.route("/dashboard/recent-documents", methods=["GET"])
@api_v1_bp.route("/dashboard/recent-documents", methods=["GET"])
def get_user_recent_documents():
    """Return top 10 most recent document jobs for the current user."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    limit = request.args.get("limit", 10)
    try:
        limit = min(max(1, int(limit)), 50)
    except (ValueError, TypeError):
        limit = 10

    engine, conn = get_active_db()
    documents = []

    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    cursor.execute("""
                        SELECT job_id, filename, file_type, file_size, document_type,
                               confidence_score, processing_time, status, current_stage,
                               error_message, created_at
                        FROM document_jobs
                        WHERE user_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (user_id, limit))
                    for row in cursor.fetchall():
                        created = row.get("created_at")
                        date_display = created.strftime("%Y-%m-%d %H:%M") if hasattr(created, "strftime") else str(created or "N/A")
                        st = row.get("status") or "Completed"
                        conf = _parse_confidence_value(row.get("confidence_score"))
                        documents.append({
                            "job_id": row["job_id"],
                            "filename": row.get("filename") or "Document",
                            "file_type": row.get("file_type") or "FILE",
                            "document_type": row.get("document_type") or "General Document",
                            "confidence": conf,
                            "confidence_score": str(row.get("confidence_score") or f"{conf}%"),
                            "status": st,
                            "stage": row.get("current_stage") or "Final Result",
                            "processing_time": str(row.get("processing_time") or "N/A"),
                            "created_at": date_display,
                            "result_url": f"/results/{row['job_id']}"
                        })
        else:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT job_id, filename, file_type, file_size, document_type,
                           confidence_score, processing_time, status, current_stage,
                           error_message, created_at
                    FROM document_jobs
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (user_id, limit))
                for r in cursor.fetchall():
                    row = dict(r)
                    created = row.get("created_at")
                    date_display = str(created)[:16] if created else "N/A"
                    try:
                        dt = datetime.strptime(str(created)[:19], "%Y-%m-%d %H:%M:%S")
                        date_display = dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        pass
                    st = row.get("status") or "Completed"
                    conf = _parse_confidence_value(row.get("confidence_score"))
                    documents.append({
                        "job_id": row["job_id"],
                        "filename": row.get("filename") or "Document",
                        "file_type": row.get("file_type") or "FILE",
                        "document_type": row.get("document_type") or "General Document",
                        "confidence": conf,
                        "confidence_score": str(row.get("confidence_score") or f"{conf}%"),
                        "status": st,
                        "stage": row.get("current_stage") or "Final Result",
                        "processing_time": str(row.get("processing_time") or "N/A"),
                        "created_at": date_display,
                        "result_url": f"/results/{row['job_id']}"
                    })
    except Exception as exc:
        logger.error("get_user_recent_documents DB error for user %s: %s", user_id, exc)
        return jsonify({"success": False, "message": "Failed to query recent documents."}), 500

    return jsonify({
        "success": True,
        "documents": documents,
        "count": len(documents),
        "empty": len(documents) == 0
    }), 200
