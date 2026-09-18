from pathlib import Path

from app.config import get_settings
from app.database import SessionLocal, engine
from app.database import Base
from app import models  # noqa: F401
from app.seed import seed


def main() -> None:
    settings = get_settings()
    Path(settings.storage_path).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
        print("Seed complete. Development credentials are labeled in README.md.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
