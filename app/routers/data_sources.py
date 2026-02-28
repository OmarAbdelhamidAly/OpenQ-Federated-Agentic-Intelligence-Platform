"""Data source router — upload CSV/XLSX/SQLite, connect SQL, list, delete."""

from __future__ import annotations

import os
import uuid
from typing import Annotated

import pandas as pd
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.data_source import DataSource
from app.models.user import User
from app.schemas.data_source import (
    DataSourceListResponse,
    DataSourceResponse,
    SQLConnectionRequest,
)
from app.services.encryption import encrypt_json, decrypt_json
from app.services.storage import save_upload_file, get_tenant_dir
from app.services.auto_analysis_service import run_auto_analysis

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/data-sources", tags=["data-sources"])


def _profile_dataframe(df: pd.DataFrame) -> dict:
    """Build a lightweight schema profile from a DataFrame."""
    return {
        "columns": [
            {
                "name": col,
                "dtype": str(df[col].dtype),
                "null_count": int(df[col].isnull().sum()),
                "unique_count": int(df[col].nunique()),
                "sample_values": df[col].dropna().head(5).tolist(),
            }
            for col in df.columns
        ],
        "row_count": len(df),
        "column_count": len(df.columns),
    }


def _profile_sqlite(file_path: str) -> dict:
    """Build a schema profile from an uploaded SQLite file.

    Uses SQLAlchemy Inspector — no raw SQL injection possible.
    Returns a dict that pipeline agents can read as schema_summary.
    """
    from sqlalchemy import create_engine, inspect, text

    conn_str = f"sqlite:///{file_path}"
    engine = create_engine(conn_str)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        result_tables = []
        for table_name in tables:
            columns = inspector.get_columns(table_name)
            col_infos = []
            for col in columns:
                col_info = {
                    "name": col["name"],
                    "dtype": str(col["type"]),
                    "nullable": col.get("nullable", True),
                }
                # Collect sample values
                try:
                    with engine.connect() as conn:
                        rows = conn.execute(
                            text(f'SELECT "{col["name"]}" FROM "{table_name}" WHERE "{col["name"]}" IS NOT NULL LIMIT 3')
                        ).fetchall()
                    col_info["sample_values"] = [str(r[0]) for r in rows]
                except Exception:
                    col_info["sample_values"] = []
                col_infos.append(col_info)

            # Row count
            try:
                with engine.connect() as conn:
                    row_count = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
            except Exception:
                row_count = None

            result_tables.append({
                "table": table_name,
                "columns": col_infos,
                "column_count": len(col_infos),
                "row_count": row_count,
            })

        return {
            "source_type": "sqlite",
            "dialect": "sqlite",
            "table_count": len(tables),
            "total_columns": sum(t["column_count"] for t in result_tables),
            "tables": result_tables,
            "all_column_names": [
                f"{t['table']}.{c['name']}"
                for t in result_tables
                for c in t["columns"]
            ],
        }
    finally:
        engine.dispose()



@router.get("", response_model=DataSourceListResponse)
async def list_data_sources(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DataSourceListResponse:
    """List all data sources for the tenant (both roles)."""
    result = await db.execute(
        select(DataSource).where(DataSource.tenant_id == current_user.tenant_id)
    )
    sources = result.scalars().all()
    return DataSourceListResponse(
        data_sources=[DataSourceResponse.model_validate(s) for s in sources]
    )


@router.post(
    "/upload",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> DataSourceResponse:
    """Upload a CSV, XLSX, SQLite (.sqlite/.db) or SQL dump (.sql) file as a data source.

    - CSV / XLSX  → stored as flat file, profiled with pandas
    - .sqlite/.db → stored as SQLite database file, schema profiled with SQLAlchemy Inspector
    - .sql        → SQL dump imported into a new SQLite file, then treated as sqlite source
    """

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    ext = os.path.splitext(file.filename)[1].lower()
    ALLOWED = (".csv", ".xlsx", ".sqlite", ".db", ".sql")
    if ext not in ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Supported file types: {', '.join(ALLOWED)}",
        )

    # Save file to tenant directory
    tenant_id_str = str(admin.tenant_id)
    file_path = await save_upload_file(file, tenant_id_str)

    # ── CSV / XLSX ──────────────────────────────────────────────────────
    if ext in (".csv", ".xlsx"):
        try:
            df = pd.read_csv(file_path) if ext == ".csv" else pd.read_excel(file_path)
            schema_json = _profile_dataframe(df)
        except Exception as e:
            os.remove(file_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse file: {e}",
            )

        source = DataSource(
            id=uuid.uuid4(),
            tenant_id=admin.tenant_id,
            type="csv",
            name=file.filename,
            file_path=file_path,
            schema_json=schema_json,
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)

        logger.info(
            "data_source_uploaded",
            tenant_id=tenant_id_str,
            user_id=str(admin.id),
            source_id=str(source.id),
            filename=file.filename,
            rows=schema_json.get("row_count", 0),
        )
        # Trigger one-time auto-analysis in background
        background_tasks.add_task(run_auto_analysis, str(source.id), db)
        return DataSourceResponse.model_validate(source)

    # ── SQLite file (.sqlite / .db) ─────────────────────────────────────
    if ext in (".sqlite", ".db"):
        try:
            schema_json = _profile_sqlite(file_path)
        except Exception as e:
            os.remove(file_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read SQLite file: {e}",
            )

        source = DataSource(
            id=uuid.uuid4(),
            tenant_id=admin.tenant_id,
            type="sql",             # treated as SQL source by the pipeline
            name=file.filename,
            file_path=file_path,   # pipeline uses this as sqlite:///file_path
            schema_json=schema_json,
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)

        logger.info(
            "sqlite_source_uploaded",
            tenant_id=tenant_id_str,
            user_id=str(admin.id),
            source_id=str(source.id),
            filename=file.filename,
        )
        # Trigger one-time auto-analysis in background
        background_tasks.add_task(run_auto_analysis, str(source.id), db)
        return DataSourceResponse.model_validate(source)

    # ── SQL dump (.sql) → import into SQLite ────────────────────────────
    if ext == ".sql":
        import sqlite3
        # Create a fresh SQLite DB next to the dump file
        sqlite_path = file_path.replace(".sql", ".sqlite")
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                sql_text = f.read()
            conn = sqlite3.connect(sqlite_path)
            conn.executescript(sql_text)
            conn.commit()
            conn.close()
            schema_json = _profile_sqlite(sqlite_path)
        except Exception as e:
            for p in (file_path, sqlite_path):
                if os.path.exists(p):
                    os.remove(p)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to import SQL dump: {e}",
            )
        finally:
            # Remove the raw dump — we only keep the SQLite file
            if os.path.exists(file_path):
                os.remove(file_path)

        source = DataSource(
            id=uuid.uuid4(),
            tenant_id=admin.tenant_id,
            type="sql",
            name=file.filename,
            file_path=sqlite_path,  # pipeline connects to this SQLite file
            schema_json=schema_json,
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)

        logger.info(
            "sql_dump_imported",
            tenant_id=tenant_id_str,
            user_id=str(admin.id),
            source_id=str(source.id),
            filename=file.filename,
        )
        # Trigger one-time auto-analysis in background
        background_tasks.add_task(run_auto_analysis, str(source.id), db)
        return DataSourceResponse.model_validate(source)


@router.post(
    "/connect-sql",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_sql(
    body: SQLConnectionRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> DataSourceResponse:
    """Connect an external SQL database as a data source (admin only).

    IMPORTANT: Please provide credentials for a READ-ONLY database user.
    This platform will only execute SELECT queries, but using a read-only
    user adds an extra layer of safety.
    """

    # Encrypt credentials
    credentials = {
        "engine": body.engine,
        "host": body.host,
        "port": body.port,
        "database": body.database,
        "username": body.username,
        "password": body.password,
    }
    encrypted = encrypt_json(credentials)

    source = DataSource(
        id=uuid.uuid4(),
        tenant_id=admin.tenant_id,
        type="sql",
        name=body.name,
        config_encrypted=encrypted,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    logger.info(
        "sql_source_connected",
        tenant_id=str(admin.tenant_id),
        user_id=str(admin.id),
        source_id=str(source.id),
        engine=body.engine,
        host=body.host,
    )
    # Trigger one-time auto-analysis in background
    background_tasks.add_task(run_auto_analysis, str(source.id), db)
    return DataSourceResponse.model_validate(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_data_source(
    source_id: uuid.UUID,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a data source (admin only)."""

    result = await db.execute(
        select(DataSource).where(
            DataSource.id == source_id,
            DataSource.tenant_id == admin.tenant_id,
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )

    # Remove file for CSV and uploaded SQLite sources
    if source.file_path and os.path.exists(source.file_path):
        os.remove(source.file_path)

    await db.delete(source)

    logger.info(
        "data_source_deleted",
        tenant_id=str(admin.tenant_id),
        user_id=str(admin.id),
        source_id=str(source.id),
    )


@router.get("/{source_id}/dashboard", response_model=DataSourceResponse)
async def get_dashboard(
    source_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DataSourceResponse:
    """Return a DataSource with its auto_analysis_json for the dashboard.

    Both admin and viewer can access this. The frontend polls this endpoint
    while auto_analysis_status == 'running' and renders charts when 'done'.
    """
    result = await db.execute(
        select(DataSource).where(
            DataSource.id == source_id,
            DataSource.tenant_id == current_user.tenant_id,
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )
    return DataSourceResponse.model_validate(source)
