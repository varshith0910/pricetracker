import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///price_tracker.db")

_engine_kwargs: dict = {}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)


# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


# Base class for all models
class Base(DeclarativeBase):
    pass


# Get a database session
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# Create tables
def create_tables():
    Base.metadata.create_all(bind=engine)
    _migrate_legacy_products_table()


def _migrate_legacy_products_table():
    """Remove obsolete product ownership fields from existing SQLite databases."""
    inspector = inspect(engine)
    if not inspector.has_table("products"):
        return
    columns = {column["name"] for column in inspector.get_columns("products")}
    obsolete_columns = {"email", "target_price", "alert_sent"}
    if not columns.intersection(obsolete_columns):
        return

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE products_migrated (
                id INTEGER NOT NULL PRIMARY KEY,
                url VARCHAR(1000) NOT NULL UNIQUE,
                title VARCHAR(500),
                image_url VARCHAR(2000),
                current_price NUMERIC(10, 2),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))
        connection.execute(text("""
            INSERT INTO products_migrated
                (id, url, title, image_url, current_price, created_at, updated_at)
            SELECT id, url, title, image_url, current_price, created_at, updated_at
            FROM products
        """))
        connection.execute(text("DROP TABLE products"))
        connection.execute(text("ALTER TABLE products_migrated RENAME TO products"))
