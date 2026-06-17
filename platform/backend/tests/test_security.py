"""Security helper tests — password hashing, JWT, PAT."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.shared import security  # noqa: E402


def test_password_hash_roundtrip():
    h = security.hash_password("s3cret")
    assert h != "s3cret"
    assert security.verify_password("s3cret", h)
    assert not security.verify_password("wrong", h)


def test_password_verify_bad_hash_is_false():
    assert security.verify_password("x", "not-a-hash") is False


def test_jwt_roundtrip():
    tok = security.create_access_token(42)
    payload = security.decode_access_token(tok)
    assert payload["sub"] == "42"


def test_pat_prefix_and_hash():
    pt = security.new_pat_plaintext()
    assert pt.startswith("kr_")
    h = security.hash_pat(pt)
    assert len(h) == 64
    assert security.hash_pat(pt) == h  # deterministic
    assert security.hash_pat(pt + "x") != h


def test_storage_safe_filename():
    from app.shared.storage import safe_filename

    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("a b/c;d.k") == "c_d.k"
    assert safe_filename("") == "file"
