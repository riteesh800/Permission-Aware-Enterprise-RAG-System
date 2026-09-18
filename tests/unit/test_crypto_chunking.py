from app.security.crypto import hash_password, password_meets_policy, verify_password
from app.chunking.splitter import split_tabular_rows, split_text


def test_password_hash_not_plaintext():
    hashed = hash_password("DevPassw0rd!x")
    assert hashed != "DevPassw0rd!x"
    assert verify_password("DevPassw0rd!x", hashed)
    assert not verify_password("wrong-password", hashed)


def test_password_policy():
    assert not password_meets_policy("short")
    assert password_meets_policy("DevPassw0rd!x")


def test_chunking_overlap_and_tables():
    text = "Paragraph one about policy.\n\nParagraph two about training.\n\nParagraph three about hours."
    chunks = split_text(text, chunk_size=8, overlap=2)
    assert chunks
    rows = split_tabular_rows(["name", "salary"], [["Alice", "1"], ["Bob", "2"]], sheet_name="comp")
    assert rows
    assert "name | salary" in rows[0].content
