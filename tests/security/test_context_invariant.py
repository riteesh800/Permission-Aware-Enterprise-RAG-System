from app.auth.service import AuthenticationService
from app import database as dbmod
from app.models.user import User
from app.retrieval.retriever import Retriever
from app.retrieval.context import build_authorized_context


def test_unauthorized_chunks_never_enter_context():
    db = dbmod.SessionLocal()
    try:
        alice = db.query(User).filter(User.unique_identifier == "ACME-100001").one()
        user = AuthenticationService(db).to_auth_user(alice)
        retriever = Retriever(db)
        chunks, _denied = retriever.retrieve(user, "CEO salary finance HR confidential files")
        context = build_authorized_context(chunks)
        assert "480000" not in context
        assert "HR employee report" not in context.lower()
        for chunk in chunks:
            assert "Finance Salary" not in chunk.document_title
            assert "HR Employee" not in chunk.document_title
    finally:
        db.close()
