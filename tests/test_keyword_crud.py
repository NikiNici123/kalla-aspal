from database import database as db


def test_add_keyword_then_duplicate_rejected(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    with db.connect(db_path) as conn:
        ok, msg = db.add_keyword(conn, "jembatan")
        assert ok is True

        ok2, msg2 = db.add_keyword(conn, "jembatan")
        assert ok2 is False
        assert "sudah ada" in msg2


def test_add_keyword_rejects_blank():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from database.models import SCHEMA_SQL
    conn.executescript(SCHEMA_SQL)
    ok, msg = db.add_keyword(conn, "   ")
    assert ok is False
    assert "kosong" in msg


def test_update_keyword_text(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    with db.connect(db_path) as conn:
        db.add_keyword(conn, "jembatan")
        row = conn.execute("SELECT id FROM keywords WHERE keyword='jembatan'").fetchone()
        ok, msg = db.update_keyword_text(conn, row["id"], "jembatan gantung")
        assert ok is True
        updated = conn.execute("SELECT keyword FROM keywords WHERE id=?", (row["id"],)).fetchone()
        assert updated["keyword"] == "jembatan gantung"


def test_set_keyword_enabled_and_get_enabled_keywords(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    with db.connect(db_path) as conn:
        db.add_keyword(conn, "jembatan")
        row = conn.execute("SELECT id FROM keywords WHERE keyword='jembatan'").fetchone()

        db.set_keyword_enabled(conn, row["id"], False)
        enabled = [k["keyword"] for k in db.get_enabled_keywords(conn)]
        assert "jembatan" not in enabled

        db.set_keyword_enabled(conn, row["id"], True)
        enabled2 = [k["keyword"] for k in db.get_enabled_keywords(conn)]
        assert "jembatan" in enabled2


def test_delete_keyword(tmp_path):
    db_path = tmp_path / "test.db"
    db.init_db(db_path)
    with db.connect(db_path) as conn:
        db.add_keyword(conn, "jembatan")
        row = conn.execute("SELECT id FROM keywords WHERE keyword='jembatan'").fetchone()
        db.delete_keyword(conn, row["id"])
        remaining = conn.execute("SELECT id FROM keywords WHERE keyword='jembatan'").fetchone()
        assert remaining is None
