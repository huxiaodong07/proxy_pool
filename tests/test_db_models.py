from app.db.base import Base
from app.db import models  # noqa: F401


def test_core_tables_registered() -> None:
    table_names = set(Base.metadata.tables.keys())
    assert {"proxies", "proxy_checks", "proxy_tags", "api_keys"}.issubset(table_names)
