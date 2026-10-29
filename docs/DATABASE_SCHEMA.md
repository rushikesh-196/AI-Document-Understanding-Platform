# Database Schema Documentation — AI Document Understanding Platform

## 1. Dual-Engine Persistence Model

The platform uses an intelligent dual-engine persistence architecture implemented in `services/database.py`:

```
              ┌────────────────────────────────────────────────────────┐
              │           Database Connection Manager                  │
              │             services/database.py                       │
              └───────────────────────────┬────────────────────────────┘
                                          │
                        ┌─────────────────┴─────────────────┐
                        │ Try Connecting to MySQL 8.0       │
                        └─────────────────┬─────────────────┘
                                          │
                        ┌─────────────────┴─────────────────┐
             Connection Successful?                         Connection Failed?
                        │                                           │
                        ▼                                           ▼
          ┌───────────────────────────┐               ┌───────────────────────────┐
          │  MySQL Engine (Primary)   │               │ SQLite Engine (Fallback)  │
          │  Database: intelligent_ocr│               │ data/document_platform.db │
          │  Full connection pooling  │               │ Embedded, zero setup      │
          └───────────────────────────┘               └───────────────────────────┘
```

---

## 2. Table Specifications (Primary Platform)

### 2.1. `users` Table
Stores authentication credentials, user roles, hierarchy relationships, and account lifecycle statuses.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | `PRIMARY KEY AUTO_INCREMENT` | Unique user identifier |
| `name` | `VARCHAR(255)` | `NOT NULL` | Full user name |
| `email` | `VARCHAR(255)` | `NOT NULL UNIQUE` | User login email address |
| `password_hash` | `VARCHAR(255)` | `NOT NULL` | Secure password hash (PBKDF2-HMAC-SHA256) |
| `role` | `VARCHAR(50)` | `NOT NULL DEFAULT 'user'` | Role: `user` or `admin` |
| `admin_id` | `INTEGER` | `NULL` | Foreign key referencing the parent managing admin |
| `status` | `VARCHAR(50)` | `NOT NULL DEFAULT 'active'`| Lifecycle: `active` or `blocked` |
| `created_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Account creation timestamp |
| `last_login` | `TIMESTAMP` | `NULL` | Last successful login timestamp |
| `updated_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Last profile update timestamp |

---

### 2.2. `document_jobs` Table
Stores ingestion metadata, OCR processing metrics, confidence scores, and structured JSON representations.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `job_id` | `VARCHAR(64)` | `PRIMARY KEY` | Unique job identifier (`JOB-XXXXXXXX`) |
| `user_id` | `INTEGER` | `NULL` | Owner user ID (or NULL for guest demo runs) |
| `filename` | `VARCHAR(255)` | `NOT NULL` | Original uploaded filename |
| `file_type` | `VARCHAR(50)` | `NULL` | MIME type / file format (`pdf`, `png`, `jpg`) |
| `file_size` | `VARCHAR(50)` | `NULL` | Formatted file size string (e.g. `245 KB`) |
| `document_type` | `VARCHAR(100)` | `NULL` | Classification category (`Invoice`, `Receipt`, etc.) |
| `confidence_score`| `VARCHAR(20)`| `NULL` | Average OCR confidence percentage (0.00 – 1.00) |
| `processing_time` | `VARCHAR(50)`| `NULL` | Execution duration in seconds |
| `status` | `VARCHAR(50)` | `DEFAULT 'Completed'` | Pipeline status: `Pending`, `Processing`, `Completed`, `Failed` |
| `current_stage` | `VARCHAR(100)`| `DEFAULT 'Final Result'` | Current stage name |
| `error_message` | `TEXT` | `NULL` | Error details if job failed |
| `summary` | `TEXT` | `NULL` | Document overview or LLM-generated summary |
| `data_json` | `LONGTEXT` | `NULL` | Complete structured analysis payload (tables, entities) |
| `created_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Job creation time |
| `updated_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Status change timestamp |

---

### 2.3. `activity_logs` Table
Maintains an immutable chronological audit trail of all security and administrative actions.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | `PRIMARY KEY AUTO_INCREMENT` | Unique log entry ID |
| `user_id` | `INTEGER` | `NULL` | Subject user ID |
| `admin_id` | `INTEGER` | `NULL` | Acting administrator ID (if initiated by an admin) |
| `action` | `VARCHAR(255)` | `NOT NULL` | Action summary (e.g., `User Login`, `Admin created`) |
| `details` | `TEXT` | `NULL` | Contextual metadata, changed fields, or parameters |
| `ip_address` | `VARCHAR(50)` | `NULL` | Client IP address |
| `created_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Action timestamp |

---

### 2.4. `error_logs` Table
Logs unhandled exceptions, OCR failures, and system errors for administrative debugging.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | `PRIMARY KEY AUTO_INCREMENT` | Unique error record ID |
| `error_type` | `VARCHAR(100)` | `NOT NULL` | Exception class or category name |
| `message` | `TEXT` | `NOT NULL` | Error message string |
| `stack_trace` | `TEXT` | `NULL` | Full execution traceback |
| `endpoint` | `VARCHAR(255)` | `NULL` | Request URI that triggered the failure |
| `created_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Exception timestamp |

---

## 3. Database Initialization & Schema Migrations

The platform automatically applies idempotent table creation and column migrations upon startup via `services/database.py:init_auth_db()`.

To manually verify or trigger database initialization:
```bash
python -c "from services.database import init_auth_db, get_active_db; init_auth_db(); engine, _ = get_active_db(); print('Active engine:', engine)"
```

## 4. Backup & Recovery

- Automatic backups of development SQLite databases are stored in `data/.backup/`.
- To create an on-demand snapshot:
  ```powershell
  Copy-Item "data\document_platform.db" "data\.backup\document_platform_manual.bak"
  ```
