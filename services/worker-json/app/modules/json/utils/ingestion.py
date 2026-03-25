"""Data Ingestion Utilities for mirroring flat-file data to Postgres.

Enables Superset and other SQL-native tools to explore non-SQL sources.
"""
import pandas as pd
import structlog
from sqlalchemy import text
from app.infrastructure.database.postgres import engine

logger = structlog.get_logger(__name__)

async def ingest_csv_to_postgres(file_path: str, table_name: str, tenant_id: str) -> bool:
    """Read a CSV and mirror it to Postgres."""
    try:
        df = pd.read_csv(file_path)
        return await ingest_to_postgres(df, table_name, tenant_id)
    except Exception as e:
        logger.error("csv_ingestion_direct_failed", error=str(e), table=table_name)
        return False

async def ingest_to_postgres(df: pd.DataFrame, table_name: str, tenant_id: str) -> bool:
    """Common logic for ingesting a DataFrame into Postgres."""
    try:
        sync_engine = getattr(engine, "sync_engine", engine)
        with sync_engine.connect() as conn:
            df.to_sql(table_name, conn, if_exists='replace', index=False, schema='public')
            try:
                conn.execute(text(f"GRANT SELECT ON public.{table_name} TO superset_user"))
                conn.commit()
            except Exception: pass
        logger.info("data_mirrored_to_postgres", table=table_name, rows=len(df))
        return True
    except Exception as e:
        logger.error("postgres_mirroring_failed", error=str(e), table=table_name)
        return False
