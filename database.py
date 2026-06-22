import os

from sqlmodel import SQLModel, Session, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./jusvagas.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
