from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine, select

from app import models  # noqa: F401 -- registers tables on SQLModel.metadata
from app.config import settings
from app.models import Athlete

connect_args = {"check_same_thread": False} if "sqlite" in settings.database_url else {}
engine = create_engine(settings.database_url, connect_args=connect_args)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def migrate_db() -> None:
    """Add columns introduced after the initial schema. SQLite ALTER TABLE has no
    IF NOT EXISTS, so we check via PRAGMA and skip existing columns."""
    migrations = {
        "plannedsession": [("hr_zone", "INTEGER"), ("structure", "TEXT")],
        "stravaactivity": [
            ("ai_summary", "TEXT"),
            ("gpx_data", "TEXT"),
            ("hr_data", "TEXT"),
            ("pace_data", "TEXT"),
        ],
    }
    with engine.connect() as conn:
        for table, cols in migrations.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for col, col_type in cols:
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
        conn.commit()


def get_session():
    with Session(engine) as session:
        yield session


def get_or_create_athlete(db: Session) -> Athlete:
    athlete = db.exec(select(Athlete)).first()
    if athlete is None:
        athlete = Athlete()
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
    return athlete
