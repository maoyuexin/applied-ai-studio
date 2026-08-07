from alembic import command
from alembic.config import Config

from .config import SERVICE_ROOT


def upgrade_database(database_url: str) -> None:
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(SERVICE_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")
