# Security & Governance — AI Document Understanding Platform

## 1. Security Architecture & Threat Model

The platform implements multi-layer defense-in-depth across authentication, authorization, session management, file ingestion, database interaction, and environment configuration.

---

## 2. Authentication & Authorization (RBAC)

### 2.1. Password Hashing
- User and administrator passwords are encrypted using `werkzeug.security.generate_password_hash`.
- Uses **PBKDF2 with HMAC-SHA256** and salt generation. Plaintext passwords are never stored or logged.

### 2.2. Role-Based Access Control (RBAC)
- All administrative routes (`/admin/*` and `/api/admin/*`) are protected by the `@admin_required` decorator.
- If an unauthenticated user attempts access, they are redirected to `/auth?portal=admin`.
- If an authenticated non-admin user attempts access, the platform raises an immediate `HTTP 403 Forbidden` response.
- **Tenant Isolation**: Admins can only view and manage users created under their organizational hierarchy (`admin_id = current_user.id`), preventing cross-tenant privilege escalation.

---

## 3. Session & Cookie Security

| Security Setting | Configuration | Protection Mechanism |
|---|---|---|
| `SESSION_COOKIE_HTTPONLY` | `True` | Prevents JavaScript access to session cookies (neutralizes XSS attacks) |
| `SESSION_COOKIE_SAMESITE` | `'Lax'` | Mitigates Cross-Site Request Forgery (CSRF) on cross-origin requests |
| `SESSION_COOKIE_SECURE` | Configurable (`false` in dev, `true` in prod) | Restricts cookie transmission exclusively to HTTPS channels |
| `PERMANENT_SESSION_LIFETIME` | Configurable | Automatically expires idle sessions |

---

## 4. File Upload Ingestion & Processing Safety

File upload processing adheres to strict validation standards:

1. **Size Enforcement**: Flask's `MAX_CONTENT_LENGTH = 16 * 1024 * 1024` restricts file payloads to a maximum of 16 MB, preventing resource exhaustion Denial of Service (DoS).
2. **Double Extension & MIME Validation**:
   - Allowed extensions: `{'jpg', 'jpeg', 'png', 'pdf', 'tiff', 'bmp', 'webp'}`.
   - Allowed MIME types: `{'image/jpeg', 'image/png', 'image/tiff', 'image/bmp', 'image/webp', 'application/pdf', 'application/x-pdf'}`.
3. **Path Traversal Prevention**:
   - Filenames are sanitized via `werkzeug.utils.secure_filename`.
   - Files are stored with uniquely generated job tokens (`JOB-<UUID-HEX>_<safe_filename>`), preventing file overwrite or arbitrary directory traversal (`../../`).

---

## 5. Database Interaction Security

- **Parameterized Queries**: All database queries across MySQL and SQLite use parameter substitution (`%s` for MySQL, `?` for SQLite). Dynamic SQL string interpolation is strictly prohibited, neutralizing SQL injection (SQLi) vectors.
- **Input Sanitization**: User fields and entity payloads are cleaned and validated before database persistence.

---

## 6. Secret Management & Governance

- **Zero Committed Secrets**: `.env` is excluded in `.gitignore`. Production secrets must never be committed to source control.
- **Sanitized Templates**: `.env.example` provides explicit placeholder values for all sensitive keys (`SECRET_KEY`, `MYSQL_PASSWORD`, `GEMINI_API_KEY`).
- **Interactive Masking**: CLI utilities (such as `backend/START_WITH_KEY.ps1`) mask sensitive API keys (`Substr(0,4)...***`) and use secure strings to prevent terminal history exposure.

---

## 7. Production Deployment Recommendations

When deploying to a public production environment:
1. Set `SESSION_COOKIE_SECURE = True` and enforce HTTPS via TLS 1.3 reverse proxy (Nginx or Cloudflare).
2. Generate a cryptographically random 32-byte hexadecimal secret key:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
3. Set `debug=False` (already defaulted to `False` in `app.py`).
4. Replace development administrator credentials with a complex, unique password.
