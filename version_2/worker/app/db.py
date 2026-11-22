import logging
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .config import settings

log = logging.getLogger(__name__)
_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            settings().database_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=True,
        )
    return _pool


@contextmanager
def tx():
    """Conexão com transação: commit no fim, rollback em erro."""
    with pool().connection() as conn:
        yield conn


def run_migrations() -> None:
    mdir = settings().migrations_dir
    with tx() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        # trava para dois processos não migrarem ao mesmo tempo
        conn.execute("SELECT pg_advisory_xact_lock(424242)")
        applied = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
        for f in sorted(mdir.glob("*.sql")):
            if f.name in applied:
                continue
            log.info("aplicando migration %s", f.name)
            conn.execute(f.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (f.name,))


def record_generation(**fields) -> None:
    """Registra uma chamada a provider (custo/tempo/erro). Nunca derruba o pipeline."""
    cols = ", ".join(fields)
    ph = ", ".join(["%s"] * len(fields))
    vals = [Jsonb(v) if isinstance(v, (dict, list)) else v for v in fields.values()]
    try:
        with tx() as conn:
            conn.execute(f"INSERT INTO generations ({cols}) VALUES ({ph})", vals)
    except Exception:  # noqa: BLE001
        log.exception("falha ao registrar generation")
