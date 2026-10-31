"""Inicialização do banco de dados."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import get_config

config = get_config()
DATABASE_URL = config.DATABASE_URL

# Engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debug
    pool_size=10,
    max_overflow=20,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency: retorna uma sessão de DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Cria todas as tabelas."""
    from app.models import Base
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("✓ Banco de dados inicializado")
