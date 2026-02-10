"""Tests for auth endpoints: login, logout, /auth/me, user management, admin seed."""
import pytest
import requests

BASE_URL = __import__("os").environ.get("API_BASE_URL", "http://localhost:18080/api")


@pytest.fixture(scope="module")
def admin_session():
    """Login as the seeded admin and return a requests.Session with auth cookie."""
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return s


class TestAdminSeed:
    def test_admin_user_exists(self, admin_session):
        """The seeded admin user should be accessible via /auth/me."""
        r = admin_session.get(f"{BASE_URL}/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"


class TestLogin:
    def test_login_success(self):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "admin"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert data["user"]["username"] == "admin"
        assert "access_token" in r.cookies

    def test_login_bad_password(self):
        r = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401

    def test_login_unknown_user(self):
        r = requests.post(f"{BASE_URL}/auth/login", json={"username": "nobody", "password": "x"})
        assert r.status_code == 401

    def test_me_unauthenticated(self):
        r = requests.get(f"{BASE_URL}/auth/me")
        assert r.status_code == 401


class TestLogout:
    def test_logout_clears_session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "admin"})
        r = s.get(f"{BASE_URL}/auth/me")
        assert r.status_code == 200

        s.post(f"{BASE_URL}/auth/logout")
        r = s.get(f"{BASE_URL}/auth/me")
        assert r.status_code == 401


class TestUserManagement:
    def test_create_user(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/auth/users", json={
            "username": "teststaff",
            "password": "staffpass",
            "display_name": "Test Staff",
            "role": "staff",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["user"]["username"] == "teststaff"
        assert data["user"]["role"] == "staff"

    def test_create_duplicate_user(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/auth/users", json={
            "username": "teststaff",
            "password": "x",
            "role": "staff",
        })
        assert r.status_code == 409

    def test_list_users(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/auth/users")
        assert r.status_code == 200
        users = r.json()["users"]
        usernames = [u["username"] for u in users]
        assert "admin" in usernames
        assert "teststaff" in usernames

    def test_staff_cannot_create_user(self, admin_session):
        """Staff role should get 403 on user creation."""
        s = requests.Session()
        s.post(f"{BASE_URL}/auth/login", json={"username": "teststaff", "password": "staffpass"})
        r = s.post(f"{BASE_URL}/auth/users", json={
            "username": "sneaky",
            "password": "x",
            "role": "staff",
        })
        assert r.status_code == 403

    def test_staff_cannot_list_users(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/auth/login", json={"username": "teststaff", "password": "staffpass"})
        r = s.get(f"{BASE_URL}/auth/users")
        assert r.status_code == 403

    def test_update_user_role(self, admin_session):
        # Get the staff user ID
        r = admin_session.get(f"{BASE_URL}/auth/users")
        staff = [u for u in r.json()["users"] if u["username"] == "teststaff"][0]

        r = admin_session.put(f"{BASE_URL}/auth/users/{staff['id']}", json={"role": "admin"})
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "admin"

        # Revert
        admin_session.put(f"{BASE_URL}/auth/users/{staff['id']}", json={"role": "staff"})

    def test_deactivate_user(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/auth/users")
        staff = [u for u in r.json()["users"] if u["username"] == "teststaff"][0]

        r = admin_session.put(f"{BASE_URL}/auth/users/{staff['id']}", json={"is_active": False})
        assert r.status_code == 200
        assert r.json()["user"]["is_active"] is False

        # Disabled user can't login
        r = requests.post(f"{BASE_URL}/auth/login", json={"username": "teststaff", "password": "staffpass"})
        assert r.status_code == 401

        # Re-enable
        admin_session.put(f"{BASE_URL}/auth/users/{staff['id']}", json={"is_active": True})

    def test_admin_reset_password(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/auth/users")
        staff = [u for u in r.json()["users"] if u["username"] == "teststaff"][0]

        r = admin_session.put(f"{BASE_URL}/auth/users/{staff['id']}/password", json={"password": "newpass"})
        assert r.status_code == 200

        # Login with new password
        s = requests.Session()
        r = s.post(f"{BASE_URL}/auth/login", json={"username": "teststaff", "password": "newpass"})
        assert r.status_code == 200

        # Reset back for other tests
        admin_session.put(f"{BASE_URL}/auth/users/{staff['id']}/password", json={"password": "staffpass"})
