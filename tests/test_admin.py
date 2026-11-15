import io

import pytest
from sqlalchemy import text

from app import admin


def test_create_md_then_log_in(client, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("a long enough password\n"))
    admin.main(["create-md", "--name", "Folake Adeyemi", "--email", "Folake@Company.test", "--password-stdin"])
    assert "Created MD" in capsys.readouterr().out
    r = client.post("/api/auth/password-login", json={"email": "folake@company.test", "password": "a long enough password"})
    assert r.status_code == 200


def test_second_md_is_refused(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("a long enough password\n"))
    admin.main(["create-md", "--name", "A", "--email", "a@company.test", "--password-stdin"])
    monkeypatch.setattr("sys.stdin", io.StringIO("a long enough password\n"))
    with pytest.raises(SystemExit):
        admin.main(["create-md", "--name", "B", "--email", "b@company.test", "--password-stdin"])
    assert "already an active MD" in capsys.readouterr().err


def test_short_password_is_refused(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("short\n"))
    with pytest.raises(SystemExit):
        admin.main(["create-md", "--name", "A", "--email", "a@company.test", "--password-stdin"])


def test_reset_md_password(client, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("first password 123\n"))
    admin.main(["create-md", "--name", "A", "--email", "a@company.test", "--password-stdin"])
    monkeypatch.setattr("sys.stdin", io.StringIO("second password 456\n"))
    admin.main(["reset-md-password", "--email", "a@company.test", "--password-stdin"])
    login = lambda pw: client.post("/api/auth/password-login", json={"email": "a@company.test", "password": pw})
    assert login("first password 123").status_code == 401
    assert login("second password 456").status_code == 200


def test_create_manager_prints_a_single_use_invite_link(owner, capsys):
    admin.main(["create-manager", "--name", "Emeka Okonkwo"])
    out = capsys.readouterr().out
    link = out.strip().splitlines()[-1]
    assert link.startswith("https://attendance.test/invite/")
    token = link.rsplit("/", 1)[1]
    assert len(token) >= 43  # 32 random bytes, base64url
    with owner.connect() as conn:
        rows = conn.execute(text(
            "SELECT i.token_hash, i.expires_at - i.created_at, i.used_at, u.role "
            "FROM invites i JOIN users u ON u.id = i.user_id")).all()
        actions = conn.execute(text("SELECT action FROM activity_log ORDER BY id")).scalars().all()
    assert len(rows) == 1
    stored, lifetime, used_at, role = rows[0]
    assert token.encode() not in bytes(stored)
    assert lifetime.total_seconds() == 48 * 3600 and used_at is None and role == "manager"
    assert actions == ["user_add", "invite_create"]


def test_second_manager_is_refused(capsys):
    admin.main(["create-manager", "--name", "Emeka"])
    with pytest.raises(SystemExit):
        admin.main(["create-manager", "--name", "Someone else"])
    assert "exactly one" in capsys.readouterr().err
