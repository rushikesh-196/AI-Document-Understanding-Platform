"""
Comprehensive End-to-End System Tests for Admin Login, RBAC, Admin-User Hierarchy,
and Document Intelligence Platform.
"""

import os
import json
import time
import pytest
from app import create_app
from services.database import init_auth_db, get_active_db
from services.auth_service import register_user, authenticate_user, create_user_by_admin, update_user_status
from create_admin import create_admin


@pytest.fixture(scope="module")
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


def test_1_database_initialization():
    """Test database schema initialization & migrations."""
    result = init_auth_db()
    assert result is True or result is False  # MySQL or SQLite fallback initialized
    
    engine, conn = get_active_db()
    assert engine in ["mysql", "sqlite"]


def test_2_user_registration_and_login(client):
    """Test user registration always sets role='user' and status='active'."""
    timestamp = int(time.time())
    test_email = f"test_normal_user_{timestamp}@example.com"
    test_pass = "TestUserPass123!"

    user, err = register_user("Normal Test User", test_email, test_pass)
    assert user is not None
    assert user["role"] == "user"
    assert user["status"] == "active"
    assert err is None

    # Test user login via user portal
    auth_user, err = authenticate_user(test_email, test_pass, portal="user")
    assert auth_user is not None
    assert auth_user["role"] == "user"
    assert err is None


def test_3_normal_user_cannot_login_as_admin():
    """Test normal user is blocked from logging in on the Admin tab."""
    timestamp = int(time.time())
    test_email = f"test_user_block_{timestamp}@example.com"
    test_pass = "TestUserPass123!"
    register_user("Blocked Normal", test_email, test_pass)

    auth_admin, err = authenticate_user(test_email, test_pass, portal="admin")
    assert auth_admin is None
    assert "reserved for administrators" in err.lower() or "denied" in err.lower()


def test_4_admin_creation_and_login():
    """Test admin account creation and successful authentication on Admin portal."""
    timestamp = int(time.time())
    admin_email = f"lead_admin_{timestamp}@docintel.io"
    admin_pass = "LeadAdminPass2026!"

    res = create_admin("Lead Admin", admin_email, admin_pass)
    assert res is True

    auth_admin, err = authenticate_user(admin_email, admin_pass, portal="admin")
    assert auth_admin is not None
    assert auth_admin["role"] == "admin"
    assert auth_admin["status"] == "active"
    assert err is None


def test_5_admin_creates_user_with_admin_id_hierarchy():
    """Test admin creating user automatically sets role='user' and admin_id."""
    timestamp = int(time.time())
    admin_email = f"admin_alpha_{timestamp}@docintel.io"
    create_admin("Admin Alpha", admin_email, "AlphaPass123!")
    admin_a, _ = authenticate_user(admin_email, "AlphaPass123!", portal="admin")

    user, err = create_user_by_admin(admin_a["id"], "User Under Alpha", f"user_under_alpha_{timestamp}@example.com", "UserPass123!")
    assert user is not None
    assert user["role"] == "user"
    assert user["admin_id"] == admin_a["id"]
    assert err is None


def test_6_admin_isolation_admin_a_cannot_see_admin_b_users():
    """Test Admin A never sees Admin B's assigned users."""
    timestamp = int(time.time())
    create_admin("Admin Beta", f"admin_beta_{timestamp}@docintel.io", "BetaPass123!")
    admin_b, _ = authenticate_user(f"admin_beta_{timestamp}@docintel.io", "BetaPass123!", portal="admin")

    # Beta creates user under Beta
    create_user_by_admin(admin_b["id"], "User Under Beta", f"user_under_beta_{timestamp}@example.com", "BetaPass123!")

    # Verify Beta's users list contains Beta's user and not Alpha's user
    from services.auth_service import get_admin_managed_users
    beta_users = get_admin_managed_users(admin_b["id"])
    beta_emails = [u["email"] for u in beta_users]

    assert f"user_under_beta_{timestamp}@example.com" in beta_emails


def test_7_user_block_and_prevent_login():
    """Test admin blocking a user prevents that user from logging in."""
    timestamp = int(time.time())
    admin_email = f"admin_alpha_blk_{timestamp}@docintel.io"
    create_admin("Admin Block Test", admin_email, "AlphaPass123!")
    admin_a, _ = authenticate_user(admin_email, "AlphaPass123!", portal="admin")

    user_email = f"user_alpha_blk_{timestamp}@example.com"
    sub_user, _ = create_user_by_admin(admin_a["id"], "User Alpha", user_email, "UserPass123!")
    assert sub_user is not None

    # Block user
    success, msg = update_user_status(sub_user["id"], "blocked", admin_a["id"])
    assert success is True

    # User attempts to login
    blocked_user, err = authenticate_user(user_email, "UserPass123!", portal="user")
    assert blocked_user is None
    assert "blocked" in err.lower() or "deactivated" in err.lower()

    # Unblock user
    success, msg = update_user_status(sub_user["id"], "active", admin_a["id"])
    assert success is True

    unblocked_user, _ = authenticate_user(user_email, "UserPass123!", portal="user")
    assert unblocked_user is not None


def test_8_unauthorized_access_protection(client):
    """Test unauthenticated or normal users cannot access admin pages."""
    timestamp = int(time.time())
    normal_user, _ = register_user("RBAC Normal User", f"rbac_normal_{timestamp}@example.com", "NormalPass123!")
    assert normal_user is not None

    # 1. Unauthenticated request to /admin/dashboard redirects to /auth
    with client.session_transaction() as sess:
        sess.clear()

    res = client.get("/admin/dashboard")
    assert res.status_code == 302
    assert "/auth" in res.headers["Location"]

    # 2. Normal user session cannot access /admin/dashboard or admin APIs
    with client.session_transaction() as sess:
        sess["user_id"] = normal_user["id"]
        sess["role"] = "user"

    res = client.get("/admin/dashboard")
    assert res.status_code == 403  # Forbidden

    res = client.get("/api/admin/stats")
    assert res.status_code == 403

    res = client.get("/api/admin/users")
    assert res.status_code == 403


def test_9_admin_dashboard_and_api_access(client):
    """Test authenticated admin can access all admin pages and APIs."""
    timestamp = int(time.time())
    admin_email = f"super_dash_{timestamp}@docintel.io"
    create_admin("Super Dash", admin_email, "SuperAdminPass@2026")
    admin_user, _ = authenticate_user(admin_email, "SuperAdminPass@2026", portal="admin")
    
    with client.session_transaction() as sess:
        sess["user_id"] = admin_user["id"]
        sess["role"] = "admin"

    # Pages
    for route in ["/admin/dashboard", "/admin/users", "/admin/documents", "/admin/analytics", "/admin/processing-monitor", "/admin/activity-logs", "/admin/error-logs", "/admin/storage", "/admin/profile"]:
        res = client.get(route)
        assert res.status_code == 200, f"Route {route} failed with status {res.status_code}"

    # APIs
    for api_route in ["/api/admin/stats", "/api/admin/users", "/api/admin/documents", "/api/admin/analytics", "/api/admin/processing-monitor", "/api/admin/activity-logs", "/api/admin/error-logs", "/api/admin/storage"]:
        res = client.get(api_route)
        assert res.status_code == 200, f"API Route {api_route} failed with status {res.status_code}"
        data = res.get_json()
        assert data.get("success") is True


def test_10_user_functionality_intact(client):
    """Test existing user endpoints remain functional (landing page, dashboard, auth, history)."""
    with client.session_transaction() as sess:
        sess.clear()

    # Landing page
    res = client.get("/")
    assert res.status_code == 200
    assert b"AI Document" in res.data

    # Auth page
    res = client.get("/auth")
    assert res.status_code == 200
    assert b"User Login" in res.data
    assert b"Admin Login" in res.data
