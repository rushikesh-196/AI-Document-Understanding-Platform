# Data & Database Policy

This directory manages persistent storage, database backups, and local development database files for the **AI Document Understanding Platform**.

## Database Overview

The platform uses a resilient **dual-engine database architecture**:

1. **MySQL (Production / Primary Engine)**:
   - Hosts tables for user management, role-based access control (RBAC), admin audit logs, error logs, and document job records.
   - Connected via `mysql-connector-python` with connection pooling and auto-reconnect.
   - Configuration is supplied via environment variables (`MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_PORT`).

2. **SQLite (Local Fallback Engine)**:
   - File path: `data/document_platform.db`
   - Automatically activates if MySQL is unreachable, allowing standalone, offline execution without database setup friction.
   - Initialized by `services/database.py:init_auth_db()`.

## Directory Contents

| Path | Purpose | In Version Control? |
|---|---|---|
| `.gitkeep` | Preserves directory structure in Git | Yes |
| `README.md` | Data management and migration documentation | Yes |
| `document_platform.db` | Local SQLite database file | No (Ignored by `.gitignore`) |
| `.backup/` | Automated and manual database checkpoints | No (Ignored by `.gitignore`) |

## Data Preservation Guidelines

- **Never delete or truncate database files directly.**
- Before running test suites or schema migrations, copy `data/document_platform.db` to `data/.backup/`.
- Document job metadata stored in `document_jobs` links directly to files in `uploads/` and structured extractions in `extracted/`.
