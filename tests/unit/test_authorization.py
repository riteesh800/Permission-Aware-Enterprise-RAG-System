from app.auth.service import AuthenticationService
from app.authorization.service import AuthorizationService
from app import database as dbmod
from app.models.document import Document
from app.models.user import User


def _auth_user(ident: str):
    db = dbmod.SessionLocal()
    try:
        user = db.query(User).filter(User.unique_identifier == ident).one()
        return AuthenticationService(db).to_auth_user(user), db
    except Exception:
        db.close()
        raise


def test_access_matrix():
    cases = {
        "Public Company Policy": {
            "ACME-100001": True,
            "ACME-100002": True,
            "ACME-100003": True,
            "ACME-100004": True,
        },
        "Engineering Architecture": {
            "ACME-100001": True,
            "ACME-100002": False,
            "ACME-100003": False,
            "ACME-100004": True,
        },
        "Finance Salary Report": {
            "ACME-100001": False,
            "ACME-100002": True,
            "ACME-100003": False,
            "ACME-100004": False,
        },
        "HR Employee Report": {
            "ACME-100001": False,
            "ACME-100002": False,
            "ACME-100003": True,
            "ACME-100004": False,
        },
        "Alice Private Review": {
            "ACME-100001": True,
            "ACME-100002": False,
            "ACME-100003": True,
            "ACME-100004": False,
        },
        "Bob Private Review": {
            "ACME-100001": False,
            "ACME-100002": True,
            "ACME-100003": True,
            "ACME-100004": False,
        },
        "Manager Strategy": {
            "ACME-100001": False,
            "ACME-100002": False,
            "ACME-100003": False,
            "ACME-100004": True,
        },
    }
    db = dbmod.SessionLocal()
    try:
        authz = AuthorizationService(db)
        for title, matrix in cases.items():
            doc = db.query(Document).filter(Document.title == title).one()
            for ident, expected in matrix.items():
                user = db.query(User).filter(User.unique_identifier == ident).one()
                auth_user = AuthenticationService(db).to_auth_user(user)
                assert authz.can_read_document(auth_user, doc) is expected, f"{ident} {title}"
    finally:
        db.close()


def test_deny_overrides_allow():
    from app.models.document import DocumentAcl
    from app.models.enums import AclPermission, PrincipalType

    db = dbmod.SessionLocal()
    try:
        alice = db.query(User).filter(User.unique_identifier == "ACME-100001").one()
        doc = db.query(Document).filter(Document.title == "Public Company Policy").one()
        deny = DocumentAcl(
            document_id=doc.id,
            principal_type=PrincipalType.USER.value,
            principal_id=alice.id,
            permission=AclPermission.DENY_READ.value,
        )
        db.add(deny)
        db.commit()
        db.refresh(doc)
        auth_user = AuthenticationService(db).to_auth_user(alice)
        assert AuthorizationService(db).can_read_document(auth_user, doc) is False
        db.delete(deny)
        db.commit()
    finally:
        db.close()
