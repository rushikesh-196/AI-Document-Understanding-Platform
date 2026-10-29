"""
Authentication & User Management Service
Supports role-based authentication (user/admin), admin-user relationships,
status management (active/blocked), activity logging, and MySQL/SQLite fallback.
"""

import json
import logging
import re
from contextlib import closing
from werkzeug.security import check_password_hash, generate_password_hash

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

from services.database import get_active_db, get_db_connection, log_activity

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def verify_password(stored_hash, password):
    """
    Unified password verifier supporting:
    - Standard Werkzeug hashes (scrypt, pbkdf2, sha256)
    - Bcrypt hashes ($2a$, $2b$, $2y$)
    - Plaintext fallback (if legacy dev account)
    Returns: (is_valid: bool, needs_rehash: bool)
    """
    if not stored_hash or not password:
        return False, False

    stored_str = str(stored_hash).strip()
    pwd_str = str(password)

    # 1. Standard Werkzeug check_password_hash
    try:
        if check_password_hash(stored_str, pwd_str):
            return True, False
    except Exception:
        pass

    # 2. Bcrypt checkpw
    if stored_str.startswith(("$2a$", "$2b$", "$2y$")):
        if BCRYPT_AVAILABLE:
            try:
                if bcrypt.checkpw(pwd_str.encode("utf-8"), stored_str.encode("utf-8")):
                    return True, True
            except Exception as e:
                logger.debug("Bcrypt check error: %s", e)

    # 3. Plaintext match fallback
    if stored_str == pwd_str:
        return True, True

    return False, False


def _update_user_password_hash(user_id, new_hash):
    """Silently upgrade old password hashes in database to Werkzeug scrypt on successful login."""
    try:
        engine, conn = get_active_db()
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor()) as cursor:
                    cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
                    conn.commit()
        else:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
                conn.commit()
    except Exception as e:
        logger.debug("Failed to upgrade password hash: %s", e)


def _public_user(row):
    """Return safe account data without exposing the password hash."""
    if not row:
        return None
    created = row.get("created_at") if isinstance(row, dict) else row["created_at"]
    last_log = row.get("last_login") if isinstance(row, dict) else row["last_login"]

    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row.get("role", "user") if isinstance(row, dict) else (row["role"] if "role" in row.keys() else "user"),
        "admin_id": row.get("admin_id") if isinstance(row, dict) else (row["admin_id"] if "admin_id" in row.keys() else None),
        "status": row.get("status", "active") if isinstance(row, dict) else (row["status"] if "status" in row.keys() else "active"),
        "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created or ""),
        "last_login": last_log.isoformat() if hasattr(last_log, "isoformat") else str(last_log or ""),
    }


def register_user(name, email, password, admin_id=None):
    """Public user registration. Always creates accounts with role='user' and status='active'."""
    name = (name or "").strip()
    email = (email or "").strip().lower()

    if len(name) < 2:
        return None, "Please enter your full name."
    if not EMAIL_PATTERN.match(email):
        return None, "Please enter a valid email address."
    if len(password or "") < 6:
        return None, "Password must be at least 6 characters."

    engine, conn = get_active_db()
    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    cursor.execute("SELECT id FROM users WHERE email = %s LIMIT 1", (email,))
                    if cursor.fetchone():
                        return None, "An account with this email already exists."

                    # If admin_id not provided, assign default primary admin if exists
                    if not admin_id:
                        cursor.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY id ASC LIMIT 1")
                        first_admin = cursor.fetchone()
                        if first_admin:
                            admin_id = first_admin["id"]

                    pw_hash = generate_password_hash(password)
                    cursor.execute(
                        "INSERT INTO users (name, email, password_hash, role, admin_id, status, created_at) VALUES (%s, %s, %s, 'user', %s, 'active', NOW())",
                        (name, email, pw_hash, admin_id),
                    )
                    conn.commit()
                    user_id = cursor.lastrowid
                    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                    user = _public_user(cursor.fetchone())
                    log_activity("User registered", user_id=user_id, admin_id=admin_id, details=f"Email: {email}")
                    return user, None
        else:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE email = ? LIMIT 1", (email,))
                if cursor.fetchone():
                    return None, "An account with this email already exists."

                if not admin_id:
                    cursor.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY id ASC LIMIT 1")
                    first_admin = cursor.fetchone()
                    if first_admin:
                        admin_id = first_admin["id"]

                pw_hash = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (name, email, password_hash, role, admin_id, status, created_at) VALUES (?, ?, ?, 'user', ?, 'active', CURRENT_TIMESTAMP)",
                    (name, email, pw_hash, admin_id),
                )
                conn.commit()
                user_id = cursor.lastrowid
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                user = _public_user(dict(cursor.fetchone()))
                log_activity("User registered", user_id=user_id, admin_id=admin_id, details=f"Email: {email}")
                return user, None
    except Exception as exc:
        logger.error("Registration error: %s", exc)
        return None, "Registration service is currently unavailable. Please try again."


def authenticate_user(email, password, portal=None, ip_address=None):
    """Authenticate user or admin, verifying password, status, and portal role requirements."""
    email = (email or "").strip().lower()
    if not email or not password:
        return None, "Email and password are required."

    engine, conn = get_active_db()
    user_row = None
    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    cursor.execute("SELECT * FROM users WHERE email = %s LIMIT 1", (email,))
                    user_row = cursor.fetchone()
        else:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE email = ? LIMIT 1", (email,))
                row = cursor.fetchone()
                if row:
                    user_row = dict(row)
    except Exception as exc:
        logger.error("Authentication query error: %s", exc)
        return None, "Authentication service is currently unavailable."

    if not user_row:
        return None, "Invalid email or password."

    stored_hash = user_row.get("password_hash")
    is_valid, needs_rehash = verify_password(stored_hash, password)
    if not is_valid:
        return None, "Invalid email or password."

    user_id = user_row["id"]

    # Silently upgrade password hash if needed
    if needs_rehash:
        try:
            new_hash = generate_password_hash(password)
            _update_user_password_hash(user_id, new_hash)
        except Exception:
            pass

    # Check status
    if user_row.get("status") == "blocked":
        return None, "Your account has been deactivated or blocked. Please contact your administrator."

    # Check role if portal is specified
    user_role = user_row.get("role", "user")
    if portal == "admin" and user_role != "admin":
        return None, "Access denied: This portal is reserved for administrators only."
    elif portal == "user" and user_role == "admin":
        # Allow admin to sign in and redirect smoothly
        pass

    # Update last_login
    try:
        engine, conn = get_active_db()
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor()) as cursor:
                    cursor.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user_id,))
                    conn.commit()
        else:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
                conn.commit()
    except Exception as e:
        logger.debug("Failed to update last_login: %s", e)

    log_activity(
        "Admin logged in" if user_role == "admin" else "User logged in",
        user_id=user_id,
        admin_id=user_row.get("admin_id"),
        ip_address=ip_address,
        details=f"Email: {email}, Portal: {portal or 'default'}"
    )

    return _public_user(user_row), None


def get_user_by_id(user_id):
    """Retrieve safe user data for an existing Flask session."""
    if not user_id:
        return None

    engine, conn = get_active_db()
    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    cursor.execute("SELECT * FROM users WHERE id = %s LIMIT 1", (user_id,))
                    return _public_user(cursor.fetchone())
        else:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE id = ? LIMIT 1", (user_id,))
                row = cursor.fetchone()
                return _public_user(dict(row)) if row else None
    except Exception as exc:
        logger.error("get_user_by_id error: %s", exc)
        return None


def create_user_by_admin(admin_id, name, email, password):
    """Admin creates a new user automatically assigned to this admin."""
    name = (name or "").strip()
    email = (email or "").strip().lower()

    if len(name) < 2:
        return None, "Please enter a valid full name."
    if not EMAIL_PATTERN.match(email):
        return None, "Please enter a valid email address."
    if len(password or "") < 6:
        return None, "Password must be at least 6 characters."

    engine, conn = "mysql", get_db_connection()
    try:
        pw_hash = generate_password_hash(password)
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    cursor.execute("SELECT id FROM users WHERE email = %s LIMIT 1", (email,))
                    if cursor.fetchone():
                        return None, "A user with this email address already exists."

                    cursor.execute(
                        "INSERT INTO users (name, email, password_hash, role, admin_id, status, created_at) VALUES (%s, %s, %s, 'user', %s, 'active', NOW())",
                        (name, email, pw_hash, admin_id),
                    )
                    conn.commit()
                    new_id = cursor.lastrowid
                    cursor.execute("SELECT * FROM users WHERE id = %s", (new_id,))
                    user = _public_user(cursor.fetchone())
                    log_activity("Admin created user", user_id=new_id, admin_id=admin_id, details=f"Created user {name} ({email})")
                    return user, None
        else:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE email = ? LIMIT 1", (email,))
                if cursor.fetchone():
                    return None, "A user with this email address already exists."

                cursor.execute(
                    "INSERT INTO users (name, email, password_hash, role, admin_id, status, created_at) VALUES (?, ?, ?, 'user', ?, 'active', CURRENT_TIMESTAMP)",
                    (name, email, pw_hash, admin_id),
                )
                conn.commit()
                new_id = cursor.lastrowid
                cursor.execute("SELECT * FROM users WHERE id = ?", (new_id,))
                user = _public_user(dict(cursor.fetchone()))
                log_activity("Admin created user", user_id=new_id, admin_id=admin_id, details=f"Created user {name} ({email})")
                return user, None
    except Exception as exc:
        logger.error("create_user_by_admin error: %s", exc)
        return None, f"Failed to create user: {str(exc)}"


def update_user_status(user_id, new_status, admin_id):
    """Toggle user status ('active' or 'blocked') strictly for assigned admin's users."""
    if new_status not in ["active", "blocked"]:
        return False, "Invalid status. Must be 'active' or 'blocked'."

    from services.admin_service import _is_global_admin
    is_global = _is_global_admin(admin_id)
    engine, conn = "mysql", get_db_connection()
    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    if is_global:
                        cursor.execute("SELECT * FROM users WHERE id = %s AND role='user' LIMIT 1", (user_id,))
                    else:
                        cursor.execute("SELECT * FROM users WHERE id = %s AND role='user' AND (admin_id = %s OR admin_id IS NULL) LIMIT 1", (user_id, admin_id))
                    user = cursor.fetchone()
                    if not user:
                        return False, "User not found or not assigned to your administration."
                    if user.get("status") == new_status:
                        return True, f"User is already {new_status}."

                    cursor.execute("UPDATE users SET status = %s WHERE id = %s", (new_status, user_id))
                    conn.commit()
                    log_activity(f"Admin {'blocked' if new_status == 'blocked' else 'activated'} user", user_id=user_id, admin_id=admin_id, details=f"User {user['email']} status changed to {new_status}")
                    return True, f"User status successfully updated to {new_status}."
        else:
            with closing(conn):
                cursor = conn.cursor()
                if is_global:
                    cursor.execute("SELECT * FROM users WHERE id = ? AND role='user' LIMIT 1", (user_id,))
                else:
                    cursor.execute("SELECT * FROM users WHERE id = ? AND role='user' AND (admin_id = ? OR admin_id IS NULL) LIMIT 1", (user_id, admin_id))
                user = cursor.fetchone()
                if not user:
                    return False, "User not found or not assigned to your administration."
                if user["status"] == new_status:
                    return True, f"User is already {new_status}."

                cursor.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
                conn.commit()
                log_activity(f"Admin {'blocked' if new_status == 'blocked' else 'activated'} user", user_id=user_id, admin_id=admin_id, details=f"User {user['email']} status changed to {new_status}")
                return True, f"User status successfully updated to {new_status}."
    except Exception as exc:
        logger.error("update_user_status error: %s", exc)
        return False, str(exc)


def delete_user_by_admin(user_id, admin_id):
    """Delete a managed user together with MySQL rows and files that depend on that account."""
    from services.admin_service import _is_global_admin, _remove_job_files
    is_global = _is_global_admin(admin_id)
    engine, conn = "mysql", get_db_connection()
    try:
        if engine == "mysql":
            saved_names = set()
            job_ids = set()
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    if is_global:
                        cursor.execute("SELECT id,name,email,role,admin_id FROM users WHERE id=%s AND role='user' LIMIT 1", (user_id,))
                    else:
                        cursor.execute("SELECT id,name,email,role,admin_id FROM users WHERE id=%s AND role='user' AND (admin_id=%s OR admin_id IS NULL) LIMIT 1", (user_id, admin_id))
                    user = cursor.fetchone()
                    if not user:
                        return False, "User not found or unauthorized to delete."

                    cursor.execute("SELECT job_id,data_json FROM document_jobs WHERE user_id=%s", (user_id,))
                    for row in cursor.fetchall():
                        if row.get("job_id"):
                            job_ids.add(str(row["job_id"]))
                        try:
                            saved = json.loads(row.get("data_json") or "{}").get("saved_file_name")
                            if saved:
                                saved_names.add(str(saved))
                        except (TypeError, ValueError):
                            pass
                    cursor.execute("SELECT job_id,saved_file_name FROM documents WHERE user_id=%s", (user_id,))
                    for row in cursor.fetchall():
                        if row.get("job_id"):
                            job_ids.add(str(row["job_id"]))
                        if row.get("saved_file_name"):
                            saved_names.add(str(row["saved_file_name"]))

                    if job_ids:
                        marks = ",".join(["%s"] * len(job_ids))
                        cursor.execute(f"DELETE FROM error_logs WHERE user_id=%s OR admin_id=%s OR job_id IN ({marks})", [user_id, user_id] + list(job_ids))
                    else:
                        cursor.execute("DELETE FROM error_logs WHERE user_id=%s OR admin_id=%s", (user_id, user_id))
                    cursor.execute("DELETE FROM documents WHERE user_id=%s", (user_id,))
                    cursor.execute("DELETE FROM document_jobs WHERE user_id=%s", (user_id,))
                    cursor.execute("DELETE FROM activity_logs WHERE user_id=%s OR admin_id=%s", (user_id, user_id))
                    cursor.execute("DELETE FROM users WHERE id=%s AND role='user'", (user_id,))
                    conn.commit()

            for job_id in job_ids:
                _remove_job_files(job_id, saved_names)
            # Keep the audit entry associated with the acting admin, never the deleted account.
            log_activity("Admin deleted user", admin_id=admin_id,
                         details=f"Deleted user {user['name']} ({user['email']}) and {len(job_ids)} linked document records")
            return True, "User and linked document records deleted successfully."

        with closing(conn):
            cursor = conn.cursor()
            if is_global:
                cursor.execute("SELECT * FROM users WHERE id=? AND role='user' LIMIT 1", (user_id,))
            else:
                cursor.execute("SELECT * FROM users WHERE id=? AND role='user' AND (admin_id=? OR admin_id IS NULL) LIMIT 1", (user_id, admin_id))
            user = cursor.fetchone()
            if not user:
                return False, "User not found or unauthorized to delete."
            cursor.execute("DELETE FROM activity_logs WHERE user_id=? OR admin_id=?", (user_id, user_id))
            cursor.execute("DELETE FROM error_logs WHERE user_id=?", (user_id,))
            cursor.execute("DELETE FROM document_jobs WHERE user_id=?", (user_id,))
            cursor.execute("DELETE FROM users WHERE id=? AND role='user'", (user_id,))
            conn.commit()
            log_activity("Admin deleted user", admin_id=admin_id, details=f"Deleted user {user['name']} ({user['email']})")
            return True, "User and linked document records deleted successfully."
    except Exception as exc:
        logger.error("delete_user_by_admin error: %s", exc)
        return False, str(exc)
def get_admin_managed_users(admin_id, search_query=None):
    """Fetch all users assigned to this admin with document count and last login.
    If this admin has no directly assigned users (global/superadmin), return all users."""
    from services.admin_service import _is_global_admin
    engine, conn = "mysql", get_db_connection()
    users = []
    search_pattern = f"%{search_query.strip()}%" if search_query else None
    is_global = _is_global_admin(admin_id)

    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    if is_global:
                        query = """
                            SELECT u.id, u.name, u.email, u.role, u.admin_id, u.status, u.created_at, u.last_login,
                                   COUNT(DISTINCT d.job_id) as doc_count,
                                   GREATEST(COALESCE(u.last_login,'1000-01-01 00:00:00'), COALESCE(MAX(d.created_at),'1000-01-01 00:00:00'), COALESCE(MAX(a.created_at),'1000-01-01 00:00:00')) as last_activity
                            FROM users u
                            LEFT JOIN document_jobs d ON d.user_id = u.id
                            LEFT JOIN activity_logs a ON a.user_id = u.id
                            WHERE u.role = 'user'
                        """
                        params = []
                    else:
                        query = """
                            SELECT u.id, u.name, u.email, u.role, u.admin_id, u.status, u.created_at, u.last_login,
                                   COUNT(DISTINCT d.job_id) as doc_count,
                                   GREATEST(COALESCE(u.last_login,'1000-01-01 00:00:00'), COALESCE(MAX(d.created_at),'1000-01-01 00:00:00'), COALESCE(MAX(a.created_at),'1000-01-01 00:00:00')) as last_activity
                            FROM users u
                            LEFT JOIN document_jobs d ON d.user_id = u.id
                            LEFT JOIN activity_logs a ON a.user_id = u.id
                            WHERE (u.admin_id = %s OR (u.admin_id IS NULL AND u.role = 'user') OR u.id = %s)
                        """
                        params = [admin_id, admin_id]
                    if search_pattern:
                        query += " AND (u.name LIKE %s OR u.email LIKE %s)"
                        params.extend([search_pattern, search_pattern])

                    query += " GROUP BY u.id ORDER BY u.created_at DESC"
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    for r in rows:
                        user_obj = _public_user(r)
                        user_obj["document_count"] = r.get("doc_count", 0)
                        activity = r.get("last_activity")
                        user_obj["last_activity"] = None if not activity or str(activity).startswith("1000-01-01") else (activity.isoformat(sep=" ", timespec="seconds") if hasattr(activity, "isoformat") else str(activity))
                        users.append(user_obj)
        else:
            with closing(conn):
                cursor = conn.cursor()
                if is_global:
                    query = """
                        SELECT u.id, u.name, u.email, u.role, u.admin_id, u.status, u.created_at, u.last_login,
                               COUNT(DISTINCT d.job_id) as doc_count,
                               MAX(COALESCE(d.created_at, u.last_login, a.created_at)) as last_activity
                        FROM users u
                        LEFT JOIN document_jobs d ON d.user_id = u.id
                        LEFT JOIN activity_logs a ON a.user_id = u.id
                        WHERE u.role = 'user'
                    """
                    params = []
                else:
                    query = """
                        SELECT u.id, u.name, u.email, u.role, u.admin_id, u.status, u.created_at, u.last_login,
                               COUNT(DISTINCT d.job_id) as doc_count,
                               MAX(COALESCE(d.created_at, u.last_login, a.created_at)) as last_activity
                        FROM users u
                        LEFT JOIN document_jobs d ON d.user_id = u.id
                        LEFT JOIN activity_logs a ON a.user_id = u.id
                        WHERE (u.admin_id = ? OR (u.admin_id IS NULL AND u.role = 'user') OR u.id = ?)
                    """
                    params = [admin_id, admin_id]
                if search_pattern:
                    query += " AND (u.name LIKE ? OR u.email LIKE ?)"
                    params.extend([search_pattern, search_pattern])

                query += " GROUP BY u.id ORDER BY u.created_at DESC"
                cursor.execute(query, params)
                for r in cursor.fetchall():
                    row_dict = dict(r)
                    user_obj = _public_user(row_dict)
                    user_obj["document_count"] = row_dict.get("doc_count", 0)
                    activity = row_dict.get("last_activity")
                    user_obj["last_activity"] = None if not activity or str(activity).startswith("1000-01-01") else (activity.isoformat(sep=" ", timespec="seconds") if hasattr(activity, "isoformat") else str(activity))
                    users.append(user_obj)
    except Exception as exc:
        logger.error("get_admin_managed_users error: %s", exc)
        if engine == "mysql":
            raise

    return users


def update_user_password(user_id, current_password, new_password):
    """Change user or admin password."""
    if len(new_password or "") < 6:
        return False, "New password must be at least 6 characters."

    engine, conn = get_active_db()
    try:
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    cursor.execute("SELECT password_hash FROM users WHERE id = %s LIMIT 1", (user_id,))
                    row = cursor.fetchone()
                    if not row:
                        return False, "User account not found."
                    is_valid, _ = verify_password(row["password_hash"], current_password)
                    if not is_valid:
                        return False, "Current password is incorrect."

                    new_hash = generate_password_hash(new_password)
                    cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
                    conn.commit()
                    log_activity("Password updated", user_id=user_id, details="User changed password")
                    return True, "Password updated successfully."
        else:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute("SELECT password_hash FROM users WHERE id = ? LIMIT 1", (user_id,))
                row = cursor.fetchone()
                if not row:
                    return False, "User account not found."
                is_valid, _ = verify_password(row["password_hash"], current_password)
                if not is_valid:
                    return False, "Current password is incorrect."

                new_hash = generate_password_hash(new_password)
                cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
                conn.commit()
                log_activity("Password updated", user_id=user_id, details="User changed password")
                return True, "Password updated successfully."
    except Exception as exc:
        logger.error("update_user_password error: %s", exc)
        return False, str(exc)


def update_admin_profile(user_id, name, email):
    """Update an administrator's public profile fields while preserving role and credentials."""
    name = (name or "").strip()
    email = (email or "").strip()
    if not name or len(name) > 255:
        return None, "Name is required and must be 255 characters or fewer."
    if not EMAIL_PATTERN.match(email) or len(email) > 255:
        return None, "Enter a valid email address of 255 characters or fewer."

    engine, conn = "mysql", get_db_connection()
    try:
        with closing(conn):
            if engine == "mysql":
                with closing(conn.cursor(dictionary=True)) as cursor:
                    cursor.execute("SELECT id,name,email,role,admin_id,status,created_at,last_login FROM users WHERE id=%s LIMIT 1", (user_id,))
                    current = cursor.fetchone()
                    if not current or current.get("role") != "admin":
                        return None, "Administrator account not found."
                    if current.get("name") == name and current.get("email") == email:
                        return _public_user(current), None
                    cursor.execute("UPDATE users SET name=%s,email=%s WHERE id=%s AND role='admin'", (name, email, user_id))
                    conn.commit()
                    cursor.execute("SELECT id,name,email,role,admin_id,status,created_at,last_login FROM users WHERE id=%s", (user_id,))
                    updated = cursor.fetchone()
            else:
                cursor = conn.cursor()
                cursor.execute("SELECT id,name,email,role,admin_id,status,created_at,last_login FROM users WHERE id=? LIMIT 1", (user_id,))
                current = cursor.fetchone()
                if not current or current["role"] != "admin":
                    return None, "Administrator account not found."
                if current["name"] == name and current["email"] == email:
                    return _public_user(dict(current)), None
                cursor.execute("UPDATE users SET name=?,email=? WHERE id=? AND role='admin'", (name, email, user_id))
                conn.commit()
                cursor.execute("SELECT id,name,email,role,admin_id,status,created_at,last_login FROM users WHERE id=?", (user_id,))
                updated = dict(cursor.fetchone())

        log_activity("Admin profile updated", user_id=user_id, admin_id=user_id, details="Administrator profile details updated")
        return _public_user(updated), None
    except Exception as exc:
        logger.error("update_admin_profile error: %s", exc)
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            return None, "That email address is already in use."
        return None, "Unable to update administrator profile."
