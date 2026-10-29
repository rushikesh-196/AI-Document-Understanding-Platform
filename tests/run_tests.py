"""
Direct Python Test Runner for Admin System & Document Intelligence Platform
"""

import os
import sys
import time

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from services.database import init_auth_db, get_active_db
from services.auth_service import (
    register_user,
    authenticate_user,
    create_user_by_admin,
    update_user_status,
    get_admin_managed_users,
)
from create_admin import create_admin


def run_all_tests():
    print("=" * 60)
    print("  RUNNING ADMIN SYSTEM & RBAC VERIFICATION SUITE")
    print("=" * 60)

    # Test 1: DB Initialization
    print("[TEST 1] Initializing database schema...")
    res = init_auth_db()
    engine, conn = get_active_db()
    print(f"  [OK] Database initialized using engine: {engine}")

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    # Test 2: User Registration & Login
    print("\n[TEST 2] Testing User Registration & Normal Login...")
    timestamp = int(time.time())
    alice_email = f"alice_{timestamp}@example.com"
    user, err = register_user("Alice Normal User", alice_email, "AlicePass123!")
    assert user is not None, f"Registration failed: {err}"
    assert user["role"] == "user", f"Expected role 'user', got {user['role']}"
    assert user["status"] == "active", f"Expected status 'active', got {user['status']}"
    print(f"  [OK] User registered: {user['email']} (role: {user['role']}, status: {user['status']})")

    auth_user, err = authenticate_user(alice_email, "AlicePass123!", portal="user")
    assert auth_user is not None, f"Auth failed: {err}"
    assert auth_user["role"] == "user"
    print("  [OK] User login authenticated successfully on User portal")

    # Test 3: Normal user cannot login on Admin portal
    print("\n[TEST 3] Testing Normal User blocked on Admin Portal...")
    admin_auth, err = authenticate_user(alice_email, "AlicePass123!", portal="admin")
    assert admin_auth is None, "Normal user should not authenticate on admin portal!"
    assert "reserved for administrators" in err.lower() or "denied" in err.lower(), f"Unexpected error: {err}"
    print(f"  [OK] Admin portal denied normal user as expected: '{err}'")

    # Test 4: Admin Account Creation and Admin Portal Login
    print("\n[TEST 4] Testing Admin Creation and Admin Login...")
    admin_email = f"superadmin_{timestamp}@docintel.io"
    admin_created = create_admin("Super Admin", admin_email, "SuperAdminPass@2026")
    assert admin_created is True
    admin_user, err = authenticate_user(admin_email, "SuperAdminPass@2026", portal="admin")
    assert admin_user is not None, f"Admin login failed: {err}"
    assert admin_user["role"] == "admin"
    print(f"  [OK] Admin authenticated: {admin_user['email']} (role: {admin_user['role']})")

    # Test 5: Admin-User Relationship Hierarchy
    print("\n[TEST 5] Testing Admin creating user under Admin hierarchy...")
    orga_email = f"admin_orga_{timestamp}@docintel.io"
    create_admin("Admin OrgA", orga_email, "OrgAPass123!")
    admin_a, _ = authenticate_user(orga_email, "OrgAPass123!", portal="admin")
    
    bob_email = f"bob_orga_{timestamp}@example.com"
    sub_user, err = create_user_by_admin(admin_a["id"], "Bob OrgA User", bob_email, "BobPass123!")
    assert sub_user is not None, f"Failed to create sub user: {err}"
    assert sub_user["role"] == "user"
    assert sub_user["admin_id"] == admin_a["id"]
    print(f"  [OK] Created user assigned to admin: admin_id={sub_user['admin_id']}")

    # Test 6: Admin Isolation (Admin A cannot see Admin B users)
    print("\n[TEST 6] Testing Admin A vs Admin B Isolation...")
    orgb_email = f"admin_orgb_{timestamp}@docintel.io"
    create_admin("Admin OrgB", orgb_email, "OrgBPass123!")
    admin_b, _ = authenticate_user(orgb_email, "OrgBPass123!", portal="admin")

    charlie_email = f"charlie_orgb_{timestamp}@example.com"
    create_user_by_admin(admin_b["id"], "Charlie OrgB User", charlie_email, "CharliePass123!")

    # Check Admin A's list
    users_a = get_admin_managed_users(admin_a["id"])
    emails_a = [u["email"] for u in users_a]
    assert bob_email in emails_a
    assert charlie_email not in emails_a

    # Check Admin B's list
    users_b = get_admin_managed_users(admin_b["id"])
    emails_b = [u["email"] for u in users_b]
    assert charlie_email in emails_b
    assert bob_email not in emails_b
    print("  [OK] Isolation verified: Admin A and Admin B cannot see each other's users")

    # Test 7: Blocking & Activating User
    print("\n[TEST 7] Testing Blocking and Activating Users...")
    update_user_status(sub_user["id"], "blocked", admin_a["id"])
    blocked_res, err = authenticate_user(bob_email, "BobPass123!", portal="user")
    assert blocked_res is None
    assert "blocked" in err.lower() or "deactivated" in err.lower()
    print(f"  [OK] Blocked user denied login: '{err}'")

    update_user_status(sub_user["id"], "active", admin_a["id"])
    unblocked_res, err = authenticate_user(bob_email, "BobPass123!", portal="user")
    assert unblocked_res is not None
    print("  [OK] Reactivated user can login again")

    # Test 8: Protected Route RBAC Authorization
    print("\n[TEST 8] Testing Route Security and RBAC Protection...")
    # Unauthenticated -> redirect 302
    with client.session_transaction() as sess:
        sess.clear()

    res = client.get("/admin/dashboard")
    assert res.status_code == 302
    print("  [OK] Unauthenticated access to /admin/dashboard redirected (302)")

    # Normal user -> 403 Forbidden
    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["role"] = "user"
    res = client.get("/admin/dashboard")
    assert res.status_code == 403
    res = client.get("/api/admin/stats")
    assert res.status_code == 403
    print("  [OK] Normal user access to /admin/* returned 403 Forbidden")

    # Admin user -> 200 OK
    with client.session_transaction() as sess:
        sess["user_id"] = admin_user["id"]
        sess["role"] = "admin"

    for path in [
        "/admin/dashboard",
        "/admin/users",
        "/admin/documents",
        "/admin/analytics",
        "/admin/processing-monitor",
        "/admin/activity-logs",
        "/admin/error-logs",
        "/admin/storage",
        "/admin/profile"
    ]:
        res = client.get(path)
        assert res.status_code == 200, f"Failed for path {path}: {res.status_code}"
    print("  [OK] Admin user successfully accessed all 9 Admin Dashboard routes (200 OK)")

    # Test 9: Admin REST APIs
    print("\n[TEST 9] Testing Admin REST APIs...")
    for api_path in [
        "/api/admin/stats",
        "/api/admin/users",
        "/api/admin/documents",
        "/api/admin/analytics",
        "/api/admin/processing-monitor",
        "/api/admin/activity-logs",
        "/api/admin/error-logs",
        "/api/admin/storage"
    ]:
        res = client.get(api_path)
        assert res.status_code == 200, f"API failed {api_path}: {res.status_code}"
        data = res.get_json()
        assert data.get("success") is True
    print("  [OK] All Admin REST API endpoints responded with HTTP 200 and success=True")

    # Test 10: Preserved User Functionality
    print("\n[TEST 10] Testing Existing User Functionality...")
    with client.session_transaction() as sess:
        sess.clear()

    res = client.get("/")
    assert res.status_code == 200
    assert b"AI Document" in res.data

    res = client.get("/auth")
    assert res.status_code == 200
    assert b"User Login" in res.data
    assert b"Admin Login" in res.data
    print("  [OK] Landing page and auth pages verified intact for guest visitors")

    print("\n" + "=" * 60)
    print("  ALL 10/10 TEST SUITES PASSED SUCCESSFULLY!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
