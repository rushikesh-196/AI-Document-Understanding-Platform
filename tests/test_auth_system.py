import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import Config
from app import create_app
from services.auth_service import register_user, authenticate_user, get_user_by_id
from services.database import get_db_connection, init_auth_db



class TestAuthSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_01_db_schema_initialization(self):
        """Verify init_auth_db creates database and users table with 'name' column."""
        self.assertTrue(init_auth_db())
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("DESCRIBE users")
        columns = {col["Field"] for col in cursor.fetchall()}
        cursor.close()
        conn.close()

        self.assertIn("id", columns)
        self.assertIn("name", columns)
        self.assertIn("email", columns)
        self.assertIn("password_hash", columns)
        self.assertIn("created_at", columns)

    def test_02_full_auth_flow(self):
        """Test full registration, mysql check, valid login, invalid password, non-existing email, logout, protected routes."""
        test_email = "testuser_2026@example.com"
        test_name = "Test User 2026"
        test_password = "Password@123"

        # Cleanup existing test user if present
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE email = %s", (test_email,))
        conn.commit()
        cursor.close()
        conn.close()

        # Step 1: Register new account
        reg_resp = self.client.post(
            "/auth/register",
            json={"name": test_name, "email": test_email, "password": test_password},
        )
        self.assertEqual(reg_resp.status_code, 201)
        reg_data = reg_resp.get_json()
        self.assertTrue(reg_data["success"])
        self.assertEqual(reg_data["user"]["email"], test_email)
        self.assertEqual(reg_data["user"]["name"], test_name)
        self.assertNotIn("password_hash", reg_data["user"])

        # Step 2: Verify user appears in MySQL users table
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (test_email,))
        db_user = cursor.fetchone()
        cursor.close()
        conn.close()
        self.assertIsNotNone(db_user)
        self.assertEqual(db_user["name"], test_name)
        self.assertEqual(db_user["email"], test_email)
        self.assertIn("password_hash", db_user)

        # Step 3: Login with correct email/password
        login_resp = self.client.post(
            "/auth/login",
            json={"email": test_email, "password": test_password},
        )
        self.assertEqual(login_resp.status_code, 200)
        login_data = login_resp.get_json()
        self.assertTrue(login_data["success"])
        self.assertEqual(login_data["user"]["email"], test_email)

        # Step 4: Verify Flask Session and access to protected route (/dashboard)
        session_resp = self.client.get("/auth/session")
        self.assertEqual(session_resp.status_code, 200)
        self.assertTrue(session_resp.get_json()["authenticated"])

        dash_resp = self.client.get("/dashboard")
        self.assertEqual(dash_resp.status_code, 200)

        # Step 5: Test login with incorrect password
        bad_pass_resp = self.client.post(
            "/auth/login",
            json={"email": test_email, "password": "WrongPassword123!"},
        )
        self.assertEqual(bad_pass_resp.status_code, 401)
        bad_pass_data = bad_pass_resp.get_json()
        self.assertFalse(bad_pass_data["success"])
        self.assertEqual(bad_pass_data["message"], "Invalid email or password.")

        # Step 6: Test login with non-existing email
        no_user_resp = self.client.post(
            "/auth/login",
            json={"email": "nonexistent_email_99@example.com", "password": "Password123"},
        )
        self.assertEqual(no_user_resp.status_code, 401)
        no_user_data = no_user_resp.get_json()
        self.assertFalse(no_user_data["success"])
        self.assertEqual(no_user_data["message"], "Invalid email or password.")

        # Step 7: Logout
        logout_resp = self.client.post("/auth/logout")
        self.assertEqual(logout_resp.status_code, 200)
        self.assertTrue(logout_resp.get_json()["success"])

        # Step 8: Verify protected page cannot be accessed without login
        unauth_dash = self.client.get("/dashboard")
        self.assertEqual(unauth_dash.status_code, 302)
        self.assertIn("/auth", unauth_dash.headers["Location"])

    def test_03_separate_pages_and_routes(self):
        """Verify /auth and /register endpoints render expected UI elements."""
        # 1. /auth page
        auth_resp = self.client.get("/auth")
        self.assertEqual(auth_resp.status_code, 200)
        auth_html = auth_resp.get_data(as_text=True)

        # Top User Login & Admin Login buttons preserved
        self.assertIn("User Login", auth_html)
        self.assertIn("Admin Login", auth_html)
        self.assertIn("portal-switcher", auth_html)

        # Sub-tabs removed from login form
        self.assertNotIn('class="user-subtabs"', auth_html)
        self.assertNotIn('id="signInTabBtn"', auth_html)
        self.assertNotIn('id="createAccTabBtn"', auth_html)

        # Blue Create Account link pointing to /register
        self.assertIn('href="/register">Create Account</a>', auth_html)

        # 2. /register page
        reg_page_resp = self.client.get("/register")
        self.assertEqual(reg_page_resp.status_code, 200)
        reg_html = reg_page_resp.get_data(as_text=True)

        # Required registration fields
        self.assertIn("Full Name", reg_html)
        self.assertIn("Email Address", reg_html)
        self.assertIn("Password", reg_html)
        self.assertIn("Confirm Password", reg_html)
        self.assertIn('id="regName"', reg_html)
        self.assertIn('id="regEmail"', reg_html)
        self.assertIn('id="regPassword"', reg_html)
        self.assertIn('id="regConfirmPassword"', reg_html)

        # Sign In link back to /auth
        self.assertIn('href="/auth">Sign In</a>', reg_html)


if __name__ == "__main__":
    unittest.main()

