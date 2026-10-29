"""
Command-Line Utility to Create / Initialize Admin Accounts
Usage:
    python create_admin.py --name "Admin Name" --email "admin@example.com" --password "Password123"
    python create_admin.py  (interactive prompt)
"""

import argparse
import sys
from getpass import getpass
from werkzeug.security import generate_password_hash

from services.database import get_active_db, init_auth_db, log_activity


def create_admin(name, email, password):
    init_auth_db()
    name = (name or "").strip()
    email = (email or "").strip().lower()
    password = (password or "").strip()

    if not name:
        print("[ERROR] Name cannot be empty.")
        return False
    if not email or "@" not in email:
        print("[ERROR] Valid email address is required.")
        return False
    if len(password) < 6:
        print("[ERROR] Password must be at least 6 characters.")
        return False

    pw_hash = generate_password_hash(password)
    engine, conn = get_active_db()

    try:
        if engine == "mysql":
            with conn:
                with conn.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT id, role FROM users WHERE email = %s LIMIT 1", (email,))
                    existing = cursor.fetchone()
                    if existing:
                        cursor.execute("""
                            UPDATE users
                            SET name = %s, password_hash = %s, role = 'admin', status = 'active'
                            WHERE id = %s
                        """, (name, pw_hash, existing["id"]))
                        conn.commit()
                        print(f"[OK] Existing user {email} promoted/updated to Admin (ID: {existing['id']})")
                        log_activity("Admin updated via CLI", user_id=existing["id"], details=f"Admin {email} updated")
                        return True
                    else:
                        cursor.execute("""
                            INSERT INTO users (name, email, password_hash, role, status, created_at)
                            VALUES (%s, %s, %s, 'admin', 'active', NOW())
                        """, (name, email, pw_hash))
                        conn.commit()
                        admin_id = cursor.lastrowid
                        print(f"[OK] Admin account created successfully: {email} (ID: {admin_id})")
                        log_activity("Admin created via CLI", user_id=admin_id, details=f"Admin {email} created")
                        return True
        else:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, role FROM users WHERE email = ? LIMIT 1", (email,))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute("""
                        UPDATE users
                        SET name = ?, password_hash = ?, role = 'admin', status = 'active'
                        WHERE id = ?
                    """, (name, pw_hash, existing["id"]))
                    conn.commit()
                    print(f"[OK] Existing user {email} promoted/updated to Admin (ID: {existing['id']})")
                    log_activity("Admin updated via CLI", user_id=existing["id"], details=f"Admin {email} updated")
                    return True
                else:
                    cursor.execute("""
                        INSERT INTO users (name, email, password_hash, role, status, created_at)
                        VALUES (?, ?, ?, 'admin', 'active', CURRENT_TIMESTAMP)
                    """, (name, email, pw_hash))
                    conn.commit()
                    admin_id = cursor.lastrowid
                    print(f"[OK] Admin account created successfully: {email} (ID: {admin_id})")
                    log_activity("Admin created via CLI", user_id=admin_id, details=f"Admin {email} created")
                    return True
    except Exception as e:
        print(f"[ERROR] Failed to create admin: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or update an Admin account for AI Document Understanding Platform.")
    parser.add_argument("--name", help="Admin Full Name", default=None)
    parser.add_argument("--email", help="Admin Email Address", default=None)
    parser.add_argument("--password", help="Admin Password", default=None)

    args = parser.parse_args()

    name = args.name
    email = args.email
    password = args.password

    if not name or not email or not password:
        print("=" * 60)
        print("  AI Document Intelligence Platform — Create Admin Account")
        print("=" * 60)
        if not name:
            name = input("Enter Admin Full Name: ").strip()
        if not email:
            email = input("Enter Admin Email: ").strip()
        if not password:
            password = getpass("Enter Admin Password (min 6 chars): ").strip()

    success = create_admin(name, email, password)
    sys.exit(0 if success else 1)
