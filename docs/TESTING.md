# Testing Guide & Verification Suite — AI Document Understanding Platform

## 1. Test Architecture Overview

The platform includes a test suite covering unit tests, integration tests, RBAC security verification, and layout reconstruction algorithms:

| Test File | Focus Area | Assertions Covered | Status |
|---|---|---|---|
| `test_admin_system.py` | Admin RBAC & Tenant Isolation | Admin creation, portal denial for users, cross-admin isolation, user block/reactivation | ✅ **10 Passed** |
| `test_auth_system.py` | User Authentication & Hashing | Registration, duplicate email rejection, PBKDF2 hash verification, session login | ✅ **3 Passed** |
| `test_dashboard_routes.py` | Dashboard Views & REST APIs | Status codes, filter query parameters, aggregated statistics | ✅ **7 Passed** |
| `test_document_intelligence.py` | Extraction Synthesis & Tables | Entity consolidation, table normalization, structured output verification | ✅ **3 Passed** |
| `test_export_service.py` | Report Generation | Dynamic PDF rendering, CSV column alignment, formatting | ✅ **1 Passed** |
| `test_layout_reconstruction.py`| Spatial Document Layout | Bounding box clustering, reading order sorting, multi-column alignment | ✅ **6 Passed** |
| **Total Automated Tests** | | | **30 Passed (100%)** |

---

## 2. Executing Automated Tests

### 2.1. Standard Pytest Runner

Ensure your virtual environment is active:

```powershell
.\venv\Scripts\Activate.ps1
pytest tests/
```

**Expected Output:**
```
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-9.1.1
collected 30 items

tests\test_admin_system.py ..........                                    [ 33%]
tests\test_auth_system.py ...                                            [ 43%]
tests\test_dashboard_routes.py .......                                   [ 66%]
tests\test_document_intelligence.py ...                                  [ 76%]
tests\test_export_service.py .                                           [ 80%]
tests\test_layout_reconstruction.py ......                               [100%]

======================= 30 passed in 30.77s =======================
```

---

### 2.2. Standalone Admin System Verification Suite

Run the end-to-end admin hierarchy test runner:

```bash
python tests/run_tests.py
```

This script executes 10 sequential integration suites:
1. Database schema initialization across MySQL and SQLite.
2. User registration and normal user authentication.
3. Access denial for standard users on `/auth?portal=admin`.
4. Admin creation and administrator credential authentication.
5. Admin-user organizational hierarchy attribution (`admin_id`).
6. Tenant isolation (Admin A cannot observe or manage Admin B's users).
7. Account deactivation, blocked user login prevention, and account reactivation.
8. Route RBAC protection (`403 Forbidden` checks).
9. Admin REST API endpoint contracts.
10. Guest visitor public access integrity.

---

## 3. Frontend Compilation & Type Verification

In the `frontend/` directory, the following checks verify zero syntax, type, or bundling regressions:

### 3.1. TypeScript Compiler Check
```powershell
node .\node_modules\typescript\lib\tsc.js --noEmit
```
*Result:* **0 type errors** across all components, pages, context, and services.

### 3.2. Vite Production Bundler Check
```powershell
node .\node_modules\vite\bin\vite.js build
```
*Result:* **Built in ~7.5 seconds**, producing optimized assets in `frontend/dist`.

---

## 4. Continuous Integration (CI)

The project includes automated CI workflows via GitHub Actions (`.github/workflows/tests.yml`). On every pull request and push to `main`, a clean container spin-up executes:
1. Python 3.10 setup.
2. MySQL 8.0 container service health checks.
3. Pip dependency caching and installation.
4. spaCy model installation.
5. Full `pytest tests/` test suite execution.
