"""
Database Persistence Service
Supports MySQL with automated SQLite fallback, schema migration, activity logging, and error logging.
"""

import json
import logging
import os
import sqlite3
from contextlib import closing
from werkzeug.security import generate_password_hash
import mysql.connector
from mysql.connector import Error

from config import Config

logger = logging.getLogger(__name__)
SQLITE_DB_PATH = os.path.join(Config.BASE_DIR, "data", "document_platform.db")

DEFAULT_ADMIN_EMAIL = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@docintel.io")
DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "Admin@123456")
DEFAULT_ADMIN_NAME = os.environ.get("DEFAULT_ADMIN_NAME", "System Administrator")


def _get_sqlite_connection():
    os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_connection():
    """Return a new connection to the MySQL database."""
    try:
        return mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            port=Config.MYSQL_PORT,
            connection_timeout=5,
        )
    except Error as exc:
        logger.debug("MySQL connection failed: %s", exc)
        raise RuntimeError("Unable to connect to MySQL database.") from exc


def get_active_db():
    """Returns a tuple (engine_type, connection).
    engine_type: 'mysql' or 'sqlite'
    """
    try:
        conn = get_db_connection()
        return "mysql", conn
    except Exception:
        return "sqlite", _get_sqlite_connection()


def _ensure_sqlite_column(cursor, table, column, col_def):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    if column not in cols:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
        except Exception as e:
            logger.debug("SQLite column add %s.%s notice: %s", table, column, e)


def _ensure_mysql_column(cursor, table, column, col_def):
    cursor.execute(f"SHOW COLUMNS FROM `{table}` LIKE %s", (column,))
    if not cursor.fetchone():
        try:
            cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {col_def}")
        except Exception as e:
            logger.debug("MySQL column add %s.%s notice: %s", table, column, e)


def init_auth_db():
    """Verify database and tables schema on app initialization."""
    # 1. Initialize & Migrate SQLite schema first as guaranteed fallback
    try:
        sconn = _get_sqlite_connection()
        scursor = sconn.cursor()
        scursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                admin_id INTEGER NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        scursor.execute("""
            CREATE TABLE IF NOT EXISTS document_jobs (
                job_id TEXT PRIMARY KEY,
                user_id INTEGER NULL,
                filename TEXT,
                file_type TEXT,
                file_size TEXT,
                document_type TEXT,
                confidence_score TEXT,
                processing_time TEXT,
                status TEXT DEFAULT 'Completed',
                current_stage TEXT DEFAULT 'Final Result',
                error_message TEXT NULL,
                summary TEXT,
                data_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        scursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NULL,
                admin_id INTEGER NULL,
                action TEXT NOT NULL,
                details TEXT NULL,
                ip_address TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        scursor.execute("""
            CREATE TABLE IF NOT EXISTS error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NULL,
                admin_id INTEGER NULL,
                job_id TEXT NULL,
                document_name TEXT NULL,
                stage TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                stack_trace TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Check missing columns in existing SQLite tables
        _ensure_sqlite_column(scursor, "users", "role", "TEXT NOT NULL DEFAULT 'user'")
        _ensure_sqlite_column(scursor, "users", "admin_id", "INTEGER NULL")
        _ensure_sqlite_column(scursor, "users", "status", "TEXT NOT NULL DEFAULT 'active'")
        _ensure_sqlite_column(scursor, "users", "last_login", "TIMESTAMP NULL")
        _ensure_sqlite_column(scursor, "users", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        _ensure_sqlite_column(scursor, "document_jobs", "user_id", "INTEGER NULL")
        _ensure_sqlite_column(scursor, "document_jobs", "file_type", "TEXT")
        _ensure_sqlite_column(scursor, "document_jobs", "file_size", "TEXT")
        _ensure_sqlite_column(scursor, "document_jobs", "status", "TEXT DEFAULT 'Completed'")
        _ensure_sqlite_column(scursor, "document_jobs", "current_stage", "TEXT DEFAULT 'Final Result'")
        _ensure_sqlite_column(scursor, "document_jobs", "error_message", "TEXT NULL")
        _ensure_sqlite_column(scursor, "document_jobs", "ocr_status", "TEXT DEFAULT 'Completed'")
        _ensure_sqlite_column(scursor, "document_jobs", "extraction_status", "TEXT DEFAULT 'Completed'")
        _ensure_sqlite_column(scursor, "document_jobs", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        _ensure_sqlite_column(scursor, "activity_logs", "user_id", "INTEGER NULL")
        _ensure_sqlite_column(scursor, "activity_logs", "admin_id", "INTEGER NULL")
        _ensure_sqlite_column(scursor, "activity_logs", "ip_address", "TEXT NULL")
        _ensure_sqlite_column(scursor, "activity_logs", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        _ensure_sqlite_column(scursor, "error_logs", "stack_trace", "TEXT NULL")

        # Seed default admin if missing in SQLite
        scursor.execute("SELECT id FROM users WHERE email = ? LIMIT 1", (DEFAULT_ADMIN_EMAIL,))
        admin_row = scursor.fetchone()
        admin_hash = generate_password_hash(DEFAULT_ADMIN_PASSWORD)
        if not admin_row:
            scursor.execute("""
                INSERT INTO users (name, email, password_hash, role, status, created_at)
                VALUES (?, ?, ?, 'admin', 'active', CURRENT_TIMESTAMP)
            """, (DEFAULT_ADMIN_NAME, DEFAULT_ADMIN_EMAIL, admin_hash))
            scursor.execute("SELECT id FROM users WHERE email = ? LIMIT 1", (DEFAULT_ADMIN_EMAIL,))
            created_admin = scursor.fetchone()
            if created_admin:
                admin_id = created_admin[0]
                scursor.execute("UPDATE users SET admin_id = ? WHERE role = 'user' AND admin_id IS NULL", (admin_id,))
        else:
            scursor.execute("UPDATE users SET role = 'admin', status = 'active' WHERE email = ?", (DEFAULT_ADMIN_EMAIL,))

        # Seed default demo user if missing in SQLite
        default_user_email = "user@docintel.io"
        scursor.execute("SELECT id FROM users WHERE email = ? LIMIT 1", (default_user_email,))
        if not scursor.fetchone():
            user_hash = generate_password_hash("User@123456")
            scursor.execute("""
                INSERT INTO users (name, email, password_hash, role, status, created_at)
                VALUES ('Demo User', ?, ?, 'user', 'active', CURRENT_TIMESTAMP)
            """, (default_user_email, user_hash))

        sconn.commit()
        sconn.close()
    except Exception as e:
        logger.debug("SQLite init error: %s", e)

    # 2. Initialize & Migrate MySQL schema
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            port=Config.MYSQL_PORT,
            connection_timeout=3,
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.close()
        conn.close()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(32) NOT NULL DEFAULT 'user',
                admin_id INT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_user_email (email),
                INDEX idx_user_role (role),
                INDEX idx_user_admin (admin_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_jobs (
                job_id VARCHAR(64) PRIMARY KEY,
                user_id INT NULL,
                filename VARCHAR(255),
                file_type VARCHAR(32),
                file_size VARCHAR(32),
                document_type VARCHAR(100),
                confidence_score VARCHAR(32),
                processing_time VARCHAR(32),
                status VARCHAR(32) DEFAULT 'Completed',
                current_stage VARCHAR(64) DEFAULT 'Final Result',
                error_message TEXT NULL,
                ocr_status VARCHAR(32) DEFAULT 'Completed',
                extraction_status VARCHAR(32) DEFAULT 'Completed',
                summary TEXT,
                data_json LONGTEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_job_user (user_id),
                INDEX idx_job_status (status),
                INDEX idx_job_created (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                admin_id INT NULL,
                action VARCHAR(255) NOT NULL,
                details TEXT NULL,
                ip_address VARCHAR(64) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_act_user (user_id),
                INDEX idx_act_admin (admin_id),
                INDEX idx_act_created (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                admin_id INT NULL,
                job_id VARCHAR(64) NULL,
                document_name VARCHAR(255) NULL,
                stage VARCHAR(100) NOT NULL,
                error_type VARCHAR(100) NOT NULL,
                error_message TEXT NOT NULL,
                stack_trace TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_err_user (user_id),
                INDEX idx_err_admin (admin_id),
                INDEX idx_err_job (job_id),
                INDEX idx_err_created (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Ensure MySQL missing columns if tables already existed
        _ensure_mysql_column(cursor, "users", "role", "VARCHAR(32) NOT NULL DEFAULT 'user'")
        _ensure_mysql_column(cursor, "users", "admin_id", "INT NULL")
        _ensure_mysql_column(cursor, "users", "status", "VARCHAR(32) NOT NULL DEFAULT 'active'")
        _ensure_mysql_column(cursor, "users", "last_login", "TIMESTAMP NULL")
        _ensure_mysql_column(cursor, "users", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

        _ensure_mysql_column(cursor, "document_jobs", "user_id", "INT NULL")
        _ensure_mysql_column(cursor, "document_jobs", "file_type", "VARCHAR(32)")
        _ensure_mysql_column(cursor, "document_jobs", "file_size", "VARCHAR(32)")
        _ensure_mysql_column(cursor, "document_jobs", "status", "VARCHAR(32) DEFAULT 'Completed'")
        _ensure_mysql_column(cursor, "document_jobs", "current_stage", "VARCHAR(64) DEFAULT 'Final Result'")
        _ensure_mysql_column(cursor, "document_jobs", "error_message", "TEXT NULL")
        _ensure_mysql_column(cursor, "document_jobs", "ocr_status", "VARCHAR(32) DEFAULT 'Completed'")
        _ensure_mysql_column(cursor, "document_jobs", "extraction_status", "VARCHAR(32) DEFAULT 'Completed'")
        _ensure_mysql_column(cursor, "document_jobs", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

        _ensure_mysql_column(cursor, "activity_logs", "user_id", "INT NULL")
        _ensure_mysql_column(cursor, "activity_logs", "admin_id", "INT NULL")
        _ensure_mysql_column(cursor, "activity_logs", "ip_address", "VARCHAR(64) NULL")
        _ensure_mysql_column(cursor, "activity_logs", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        _ensure_mysql_column(cursor, "error_logs", "stack_trace", "TEXT NULL")

        # Sync timestamp column to created_at if old schema exists in activity_logs
        try:
            cursor.execute("SHOW COLUMNS FROM `activity_logs` LIKE 'timestamp'")
            if cursor.fetchone():
                cursor.execute("UPDATE `activity_logs` SET `created_at` = `timestamp` WHERE `created_at` IS NULL AND `timestamp` IS NOT NULL")
        except Exception:
            pass

        conn.commit()

        # Seed default admin in MySQL
        cursor.execute("SELECT id FROM users WHERE email = %s LIMIT 1", (DEFAULT_ADMIN_EMAIL,))
        admin_row = cursor.fetchone()
        admin_hash = generate_password_hash(DEFAULT_ADMIN_PASSWORD)
        if not admin_row:
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, status, created_at)
                VALUES (%s, %s, %s, 'admin', 'active', NOW())
            """, (DEFAULT_ADMIN_NAME, DEFAULT_ADMIN_EMAIL, admin_hash))
            conn.commit()
            cursor.execute("SELECT id FROM users WHERE email = %s LIMIT 1", (DEFAULT_ADMIN_EMAIL,))
            created_admin = cursor.fetchone()
            if created_admin:
                admin_id = created_admin[0]
                cursor.execute("UPDATE users SET admin_id = %s WHERE role = 'user' AND admin_id IS NULL", (admin_id,))
                cursor.execute("UPDATE document_jobs SET user_id = %s WHERE user_id IS NULL", (admin_id,))
                conn.commit()
        else:
            cursor.execute("UPDATE users SET role = 'admin', status = 'active' WHERE email = %s", (DEFAULT_ADMIN_EMAIL,))
            conn.commit()

        # Seed default demo user in MySQL
        default_user_email = "user@docintel.io"
        cursor.execute("SELECT id FROM users WHERE email = %s LIMIT 1", (default_user_email,))
        if not cursor.fetchone():
            user_hash = generate_password_hash("User@123456")
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, status, created_at)
                VALUES ('Demo User', %s, %s, 'user', 'active', NOW())
            """, (default_user_email, user_hash))
            conn.commit()

        cursor.close()
        conn.close()
        logger.info("MySQL database initialized successfully with full schema.")
        return True
    except Exception as exc:
        logger.info("MySQL unavailable; using SQLite & JSON persistence. Notice: %s", exc)
        return False


def log_activity(action, user_id=None, admin_id=None, details=None, ip_address=None):
    """Log user or admin action to activity_logs table."""
    try:
        engine, conn = get_active_db()
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor(dictionary=True)) as cursor:
                    acting_admin_id = admin_id
                    # If admin_id is not provided, look up user's admin_id
                    if not admin_id and user_id:
                        cursor.execute("SELECT admin_id FROM users WHERE id = %s LIMIT 1", (user_id,))
                        row = cursor.fetchone()
                        if row and row.get("admin_id"):
                            admin_id = row["admin_id"]

                    # Existing installations may have richer activity-log columns such as
                    # actor_name, target, and timestamp. Populate those required fields from
                    # the real actor/account while keeping compatibility with the simpler table.
                    cursor.execute("SHOW COLUMNS FROM `activity_logs`")
                    column_rows = cursor.fetchall()
                    available = {row.get("Field"): row for row in column_rows}
                    actor_id = acting_admin_id if acting_admin_id is not None else user_id
                    actor_role = "admin" if acting_admin_id is not None else "user"
                    actor_name = "System"
                    if actor_id is not None:
                        cursor.execute("SELECT name,email,role FROM users WHERE id=%s LIMIT 1", (actor_id,))
                        actor = cursor.fetchone()
                        if actor:
                            actor_name = actor.get("name") or actor.get("email") or actor_name
                            actor_role = actor.get("role") or actor_role

                    mapped_values = {
                        "user_id": user_id,
                        "admin_id": admin_id,
                        "actor_id": actor_id,
                        "actor_name": str(actor_name)[:128],
                        "actor_role": str(actor_role)[:32],
                        "action": str(action or "Activity")[:255],
                        "target": str(details or action or "Activity")[:255],
                        "status": "success",
                        "details": str(details) if details else None,
                        "ip_address": ip_address,
                    }
                    timestamp_columns = {"created_at", "timestamp"}
                    insert_columns = [name for name in available if name in mapped_values or name in timestamp_columns]
                    insert_values = ["NOW()" if name in timestamp_columns else "%s" for name in insert_columns]
                    params = [mapped_values[name] for name in insert_columns if name not in timestamp_columns]

                    # If a deployment has an additional required field unknown to this
                    # logger, skip the log instead of issuing an invalid partial insert.
                    unmapped_required = [
                        name for name, meta in available.items()
                        if meta.get("Null") == "NO" and meta.get("Default") is None
                        and "auto_increment" not in str(meta.get("Extra") or "").lower()
                        and name not in insert_columns
                    ]
                    if unmapped_required:
                        raise RuntimeError("Unsupported required activity log fields: " + ", ".join(unmapped_required))

                    quoted_columns = ", ".join(f"`{name}`" for name in insert_columns)
                    cursor.execute(
                        f"INSERT INTO `activity_logs` ({quoted_columns}) VALUES ({', '.join(insert_values)})",
                        params,
                    )
                    conn.commit()
        else:
            with closing(conn):
                cursor = conn.cursor()
                if not admin_id and user_id:
                    cursor.execute("SELECT admin_id FROM users WHERE id = ? LIMIT 1", (user_id,))
                    row = cursor.fetchone()
                    if row and row["admin_id"]:
                        admin_id = row["admin_id"]
                cursor.execute("""
                    INSERT INTO activity_logs (user_id, admin_id, action, details, ip_address, created_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, admin_id, action, str(details or "") if details else None, ip_address))
                conn.commit()
    except Exception as e:
        logger.debug("Failed to log activity '%s': %s", action, e)


def log_error(stage, error_type, error_message, user_id=None, admin_id=None, job_id=None, document_name=None, stack_trace=None):
    """Log OCR/AI pipeline or system error to error_logs table."""
    try:
        engine, conn = get_active_db()
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor()) as cursor:
                    if not admin_id and user_id:
                        cursor.execute("SELECT admin_id FROM users WHERE id = %s LIMIT 1", (user_id,))
                        row = cursor.fetchone()
                        if row and row[0]:
                            admin_id = row[0]
                    cursor.execute("""
                        INSERT INTO error_logs (user_id, admin_id, job_id, document_name, stage, error_type, error_message, stack_trace, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (user_id, admin_id, job_id, document_name, stage, error_type, str(error_message), str(stack_trace) if stack_trace else None))
                    conn.commit()
        else:
            with closing(conn):
                cursor = conn.cursor()
                if not admin_id and user_id:
                    cursor.execute("SELECT admin_id FROM users WHERE id = ? LIMIT 1", (user_id,))
                    row = cursor.fetchone()
                    if row and row["admin_id"]:
                        admin_id = row["admin_id"]
                cursor.execute("""
                    INSERT INTO error_logs (user_id, admin_id, job_id, document_name, stage, error_type, error_message, stack_trace, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, admin_id, job_id, document_name, stage, error_type, str(error_message), str(stack_trace) if stack_trace else None))
                conn.commit()
    except Exception as e:
        logger.debug("Failed to log error for stage '%s': %s", stage, e)


def save_document_job_record(job_data):
    """Save or update document extraction job in MySQL or fallback SQLite."""
    if not job_data or not job_data.get("job_id"):
        return False

    job_id = job_data["job_id"]
    user_id = job_data.get("user_id")
    filename = job_data.get("filename", "")
    file_type = job_data.get("file_type") or (filename.rsplit(".", 1)[-1].upper() if "." in filename else "UNKNOWN")
    file_size = job_data.get("file_size", "")
    doc_type = job_data.get("document_type", "General Document")
    conf = str(job_data.get("confidence_score", job_data.get("confidence", "95%")))
    proc_time = str(job_data.get("processing_time", "1.0s"))
    status = job_data.get("status", "Completed")
    stage = job_data.get("current_stage", "Final Result")
    error_msg = job_data.get("error_message")
    ocr_status = job_data.get("ocr_status", "Completed" if status != "Failed" or stage != "OCR" else "Failed")
    extraction_status = job_data.get("extraction_status", "Completed" if status == "Completed" else ("Processing" if status == "Processing" else "Failed"))
    summary = job_data.get("summary", "")
    data_json_str = json.dumps(job_data, ensure_ascii=False)

    engine, conn = get_active_db()
    if engine == "mysql":
        try:
            with closing(conn):
                with closing(conn.cursor()) as cursor:
                    cursor.execute("""
                        INSERT INTO document_jobs (
                            job_id, user_id, filename, file_type, file_size, document_type,
                            confidence_score, processing_time, status, current_stage, error_message,
                            ocr_status, extraction_status, summary, data_json
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            user_id = COALESCE(VALUES(user_id), user_id),
                            filename = VALUES(filename),
                            file_type = VALUES(file_type),
                            file_size = VALUES(file_size),
                            document_type = VALUES(document_type),
                            confidence_score = VALUES(confidence_score),
                            processing_time = VALUES(processing_time),
                            status = VALUES(status),
                            current_stage = VALUES(current_stage),
                            error_message = VALUES(error_message),
                            ocr_status = VALUES(ocr_status),
                            extraction_status = VALUES(extraction_status),
                            summary = VALUES(summary),
                            data_json = VALUES(data_json)
                    """, (job_id, user_id, filename, file_type, file_size, doc_type, conf, proc_time, status, stage, error_msg, ocr_status, extraction_status, summary, data_json_str))
                    conn.commit()
                    return True
        except Exception as e:
            logger.debug("Failed to save job to MySQL: %s", e)

    # SQLite fallback
    try:
        sconn = _get_sqlite_connection()
        with closing(sconn):
            scursor = sconn.cursor()
            scursor.execute("""
                INSERT OR REPLACE INTO document_jobs (
                    job_id, user_id, filename, file_type, file_size, document_type,
                    confidence_score, processing_time, status, current_stage, error_message,
                    ocr_status, extraction_status, summary, data_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_id, user_id, filename, file_type, file_size, doc_type, conf, proc_time, status, stage, error_msg, ocr_status, extraction_status, summary, data_json_str))
            sconn.commit()
            return True
    except Exception as e:
        logger.debug("Failed to save job to SQLite: %s", e)
        return False


def update_job_stage(job_id, stage, status="Processing", percent=None, message=None, error_msg=None):
    """Update current stage and status of a processing document job."""
    try:
        engine, conn = get_active_db()
        if engine == "mysql":
            with closing(conn):
                with closing(conn.cursor()) as cursor:
                    cursor.execute("""
                        UPDATE document_jobs
                        SET current_stage = %s, status = %s, error_message = %s
                        WHERE job_id = %s
                    """, (stage, status, error_msg, job_id))
                    conn.commit()
        else:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE document_jobs
                    SET current_stage = ?, status = ?, error_message = ?
                    WHERE job_id = ?
                """, (stage, status, error_msg, job_id))
                conn.commit()
    except Exception as e:
        logger.debug("Failed to update job stage: %s", e)
