from collections.abc import Generator
from pathlib import Path
from typing import Any

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

def ensure_sqlite_directory(database_url: str) -> None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return
    database_path = Path(database_url.removeprefix(prefix))
    database_path.parent.mkdir(parents=True, exist_ok=True)


class Database:
    def __init__(self, database_url: str) -> None:
        ensure_sqlite_directory(database_url)
        self.url = database_url
        self.engine: Engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False}
            if database_url.startswith("sqlite")
            else {},
        )
        if database_url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._configure_sqlite)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    @staticmethod
    def _configure_sqlite(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    def session(self) -> Session:
        return self.session_factory()


def get_session(request: Request) -> Generator[Session, None, None]:
    database: Database = request.app.state.database
    with database.session() as session:
        yield session
