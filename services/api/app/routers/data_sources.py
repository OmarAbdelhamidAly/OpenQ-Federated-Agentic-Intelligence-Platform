"""Data source router — upload CSV/XLSX/SQLite, connect SQL, Documents (PDF/DOCX/PPTX/etc.), and more."""



import io
import os
import uuid
from typing import Annotated, Optional, Any

import pandas as pd
import structlog
from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, HTTPException, Response, UploadFile, status, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.config import settings
from app.infrastructure.database.postgres import get_db
from app.infrastructure.api_dependencies import get_current_user, require_admin, verify_permission
from app.models.policy import ResourcePolicy
from app.models.data_source import DataSource
from app.models.user import User
from app.schemas.data_source import (
    DataSourceListResponse,
    DataSourceResponse,
    SQLConnectionRequest,
    GithubConnectionRequest,
)
from app.infrastructure.adapters.encryption import encrypt_json, decrypt_json
from app.infrastructure.adapters.storage import save_upload_file, get_tenant_dir
from app.use_cases.auto_analysis.service import run_auto_analysis

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


def _profile_sqlite(file_path: str) -> dict[str, Any]:
    """Build a schema profile from an uploaded SQLite file."""
    from sqlalchemy import create_engine, inspect, text
    from app.modules.sql.utils.schema_utils import infer_foreign_keys, generate_mermaid_erd

    conn_str = f"sqlite:///{file_path}"
    engine = create_engine(conn_str)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        result_tables = []
        all_fks = []

        for table_name in tables:
            columns = inspector.get_columns(table_name)
            pk_cols = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
            
            # Extract literal FKs
            fks = inspector.get_foreign_keys(table_name)
            for fk in fks:
                for idx, from_col in enumerate(fk["constrained_columns"]):
                    all_fks.append({
                        "from_table": table_name,
                        "from_col": from_col,
                        "to_table": fk["referred_table"],
                        "to_col": fk["referred_columns"][idx]
                    })

            col_infos = []
            for col in columns:
                col_info = {
                    "name": col["name"],
                    "dtype": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "primary_key": col["name"] in pk_cols,
                    "null_count": 0,
                    "unique_count": 0,
                    "sample_values": []
                }
                col_name_q = col["name"]
                try:
                    with engine.connect() as conn:
                        # unique count
                        unique_res = conn.execute(
                            text(f'SELECT COUNT(DISTINCT "{col_name_q}") FROM "{table_name}"')
                        ).scalar()
                        col_info["unique_count"] = int(unique_res or 0)
                        # null count
                        null_res = conn.execute(
                            text(f'SELECT COUNT(*) FROM "{table_name}" WHERE "{col_name_q}" IS NULL')
                        ).scalar()
                        col_info["null_count"] = int(null_res or 0)
                        # sample values
                        rows = conn.execute(
                            text(f'SELECT "{col_name_q}" FROM "{table_name}" WHERE "{col_name_q}" IS NOT NULL LIMIT 5')
                        ).fetchall()
                        col_info["sample_values"] = [str(r[0]) for r in rows]
                except Exception:
                    pass
                col_infos.append(col_info)

            # Row count...
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

        # Infer additional relationships
        final_fks = infer_foreign_keys(result_tables, all_fks)
        mermaid_erd = generate_mermaid_erd(result_tables, final_fks)

        return {
            "source_type": "sqlite",
            "dialect": "sqlite",
            "table_count": len(tables),
            "row_count": sum(t["row_count"] for t in result_tables if t["row_count"]),
            "column_count": sum(t["column_count"] for t in result_tables),
            "tables": result_tables,
            "foreign_keys": final_fks,
            "mermaid_erd": mermaid_erd,
            "all_column_names": [
                f"{t['table']}.{c['name']}"
                for t in result_tables
                for c in t["columns"]
            ],
            "columns": [
                {
                    "name": f"{t['table']}.{c['name']}",
                    "dtype": c["dtype"],
                    "null_count": c.get("null_count", 0),
                    "unique_count": c.get("unique_count", 0),
                    "sample_values": c.get("sample_values", [])
                }
                for t in result_tables
                for c in t["columns"]
            ]
        }
    finally:
        engine.dispose()



@router.get("", response_model=DataSourceListResponse)
async def list_data_sources(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DataSourceListResponse:
    """List all data sources for the tenant (both roles)."""
    # ── Phase 3: IAM Filtering ──────
    if current_user.role == "admin":
        query = select(DataSource).where(DataSource.tenant_id == current_user.tenant_id)
    else:
        # Check for explicit ALLOW policies OR sources they own (tenant-default)
        # For simplicity in this deep dive, we allow admins to see all, 
        # but viewers see only what is explicitly shared OR if they are the "owner" (if we had an owner col).
        # Fallback: Viewers can see all in tenant UNLESS a DENY exists.
        
        # More robust: Let's fetch all DENYs for this user
        deny_res = await db.execute(
            select(ResourcePolicy.resource_id).where(
                ResourcePolicy.principal_id == current_user.id,
                ResourcePolicy.effect == "deny"
            )
        )
        denied_ids = [str(r) for r in deny_res.scalars().all()]
        
        query = select(DataSource).where(DataSource.tenant_id == current_user.tenant_id)
        if denied_ids:
            query = query.where(DataSource.id.not_in([uuid.UUID(d) for d in denied_ids if d != "*"]))

    result = await db.execute(query)
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
    context_hint: Annotated[Optional[str], Form()] = None,
    indexing_mode: Annotated[Optional[str], Form()] = "deep_vision",
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

    # Guard against path traversal - handle both / and \ regardless of OS
    raw_name = file.filename.replace("\\", "/").split("/")[-1]
    safe_name = os.path.basename(raw_name)
    
    if not safe_name:
        logger.error("upload_failed_invalid_filename", filename=file.filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    ext = os.path.splitext(safe_name)[1].lower()

    # ── Universal Document types (routed to pillar.pdf Universal pipeline)
    UNIVERSAL_DOCUMENT_EXTS = {
        ".pdf", ".docx", ".doc", ".odt", ".rtf",
        ".pptx", ".ppt",
        ".epub", ".html", ".htm", ".xml",
        ".eml", ".msg",
        ".txt", ".md",
    }

    ALLOWED = (
        # Universal Documents
        *UNIVERSAL_DOCUMENT_EXTS,
        # Structured data
        ".csv", ".xlsx", ".sqlite", ".db", ".sql", ".json", ".tsv",
        # Code
        ".zip", ".py", ".js", ".ts", ".env", ".java",
        ".cpp", ".h", ".go", ".sh", ".yaml", ".yml",
        # Media
        ".jpg", ".jpeg", ".png", ".webp",
        ".mp3", ".wav", ".m4a", ".ogg",
        ".mp4", ".mov", ".avi", ".mkv",
    )
    if ext not in ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Supported file types: {', '.join(sorted(ALLOWED))}",
        )

    # Enforce upload size limit BEFORE writing to disk
    MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_BYTES:
        logger.error("upload_failed_too_large", size=len(contents), max=MAX_BYTES)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )
    
    # Reset the file-like object so the rest of the handler can re-read it
    await file.seek(0)

    # Save file to tenant directory
    tenant_id_str = str(admin.tenant_id)
    file_path = await save_upload_file(file, tenant_id_str)

    # ── Universal Documents (PDF, DOCX, PPTX, TXT, MD, HTML, EPUB, EML, ODT, RTF, etc.) ───
    if ext in UNIVERSAL_DOCUMENT_EXTS:
        # Use extension as display type (e.g. "docx", "pptx", "pdf")
        display_type = ext.lstrip(".")

        schema_json = {
            "source_type": display_type,
            "file_extension": ext,
            "indexing_mode": indexing_mode or "fast_text",
            "progress": 0,
            "current_step": "Queued for Universal Document Intelligence pipeline...",
        }

        source = DataSource(
            id=uuid.uuid4(),
            tenant_id=admin.tenant_id,
            type=display_type,
            name=file.filename,
            file_path=file_path,
            context_hint=context_hint,
            schema_json=schema_json,
            indexing_status="running",
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)

        logger.info(
            "universal_doc_source_uploaded",
            tenant_id=tenant_id_str,
            user_id=str(admin.id),
            source_id=str(source.id),
            filename=file.filename,
            ext=ext,
        )
        from app.worker import celery_app
        celery_app.send_task(
            "process_source_indexing",
            args=[str(source.id)],
            queue="knowledge",
        )
        return DataSourceResponse.model_validate(source)


    # ── Codebase (Individual Files) ──────────────────────────────────────────
    if ext in (".py", ".js", ".ts", ".env", ".java", ".cpp", ".h", ".go", ".sh", ".yaml", ".yml"):
        schema_json = {"source_type": "codebase", "format": "single_file"}
        source = DataSource(
            id=uuid.uuid4(),
            tenant_id=admin.tenant_id,
            type="codebase",
            name=file.filename,
            file_path=file_path,
            context_hint=context_hint,
            schema_json=schema_json,
            indexing_status="running",
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)

        logger.info(
            "codebase_file_uploaded",
            tenant_id=tenant_id_str,
            user_id=str(admin.id),
            source_id=str(source.id),
            filename=file.filename,
        )
        from app.worker import celery_app
        celery_app.send_task("process_codebase_indexing", args=[str(source.id)], queue="pillar.code")
        return DataSourceResponse.model_validate(source)

    # ── JSON Document ───────────────────────────────────────────────────
    if ext == ".json":
        schema_json: dict[str, Any] = {"source_type": "json"}
        try:
            import json as json_lib
            await file.seek(0)
            raw_data = await file.read()
            json_data = json_lib.loads(raw_data)
            if isinstance(json_data, list):
                schema_json["item_count"] = len(json_data)
            elif isinstance(json_data, dict):
                schema_json["key_count"] = len(json_data.keys())
        except Exception:
            pass

        source = DataSource(
            id=uuid.uuid4(),
            tenant_id=admin.tenant_id,
            type="json",
            name=file.filename,
            file_path=file_path,
            context_hint=context_hint,
            schema_json=schema_json,
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)

        logger.info(
            "json_source_uploaded",
            tenant_id=tenant_id_str,
            user_id=str(admin.id),
            source_id=str(source.id),
            filename=file.filename,
        )
        from app.worker import celery_app
        celery_app.send_task("process_source_discovery", args=[str(source.id), str(admin.id)], queue="pillar.json")
        return DataSourceResponse.model_validate(source)

    # ── Codebase ZIP ──────────────────────────────────────────────────────
    if ext == ".zip":
        schema_json: dict[str, Any] = {"source_type": "codebase", "format": "zip"}
        source = DataSource(
            id=uuid.uuid4(),
            tenant_id=admin.tenant_id,
            type="codebase",
            name=file.filename,
            file_path=file_path,
            context_hint=context_hint,
            schema_json=schema_json,
            indexing_status="running",
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)

        logger.info(
            "codebase_zip_uploaded",
            tenant_id=tenant_id_str,
            user_id=str(admin.id),
            source_id=str(source.id),
            filename=file.filename,
        )
        from app.worker import celery_app
        celery_app.send_task("process_codebase_indexing", args=[str(source.id)], queue="pillar.code")
        return DataSourceResponse.model_validate(source)

    # ── CSV / XLSX ──────────────────────────────────────────────────────
    if ext in (".csv", ".xlsx"):
        try:
            df = pd.read_csv(file_path) if ext == ".csv" else pd.read_excel(file_path)
            schema_json = _profile_dataframe(df)
        except Exception as e:
            logger.error("file_parsing_failed", error=str(e), file_path=file_path, ext=ext)
            if os.path.exists(file_path):
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
            context_hint=context_hint,
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
        from app.worker import celery_app
        celery_app.send_task("process_source_discovery", args=[str(source.id), str(admin.id)], queue="pillar.csv")
        return DataSourceResponse.model_validate(source)

    # ── Image Document ──────────────────────────────────────────────────
    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        schema_json: dict[str, Any] = {"source_type": "image"}
        source = DataSource(
            id=uuid.uuid4(),
            tenant_id=admin.tenant_id,
            type="image",
            name=file.filename,
            file_path=file_path,
            context_hint=context_hint,
            schema_json=schema_json,
            indexing_status="running",
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)

        logger.info("image_source_uploaded", tenant_id=tenant_id_str, source_id=str(source.id), filename=file.filename)
        from app.worker import celery_app
        celery_app.send_task("process_source_discovery", args=[str(source.id), str(admin.id)], queue="pillar.image")
        return DataSourceResponse.model_validate(source)

    # ── Audio Document ──────────────────────────────────────────────────
    if ext in (".mp3", ".wav", ".m4a", ".ogg"):
        schema_json: dict[str, Any] = {"source_type": "audio"}
        source = DataSource(
            id=uuid.uuid4(),
            tenant_id=admin.tenant_id,
            type="audio",
            name=file.filename,
            file_path=file_path,
            context_hint=context_hint,
            schema_json=schema_json,
            indexing_status="running",
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)

        logger.info("audio_source_uploaded", tenant_id=tenant_id_str, source_id=str(source.id), filename=file.filename)
        from app.worker import celery_app
        celery_app.send_task("process_source_discovery", args=[str(source.id), str(admin.id)], queue="pillar.audio")
        return DataSourceResponse.model_validate(source)

    # ── Video Document ──────────────────────────────────────────────────
    if ext in (".mp4", ".mov", ".avi", ".mkv"):
        schema_json: dict[str, Any] = {"source_type": "video"}
        source = DataSource(
            id=uuid.uuid4(),
            tenant_id=admin.tenant_id,
            type="video",
            name=file.filename,
            file_path=file_path,
            context_hint=context_hint,
            schema_json=schema_json,
            indexing_status="running",
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)

        logger.info("video_source_uploaded", tenant_id=tenant_id_str, source_id=str(source.id), filename=file.filename)
        from app.worker import celery_app
        celery_app.send_task("process_source_discovery", args=[str(source.id), str(admin.id)], queue="pillar.video")
        return DataSourceResponse.model_validate(source)

    # ── SQLite file (.sqlite / .db) ─────────────────────────────────────
    if ext in (".sqlite", ".db"):
        try:
            schema_json = _profile_sqlite(file_path)
        except Exception as e:
            logger.error("sqlite_profiling_failed", error=str(e), file_path=file_path)
            if os.path.exists(file_path):
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
            context_hint=context_hint,
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
        from app.worker import celery_app
        celery_app.send_task("process_source_discovery", args=[str(source.id), str(admin.id)], queue="pillar.sql")
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
            context_hint=context_hint,
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
        # Trigger discovery/profiling phase
        from app.worker import celery_app
        celery_app.send_task("process_source_discovery", args=[str(source.id), str(admin.id)], queue="pillar.sql")
        return DataSourceResponse.model_validate(source)


@router.post(
    "/connect-sql",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_sql(
    body: Annotated[SQLConnectionRequest, Body()],
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
    from app.worker import celery_app
    celery_app.send_task("auto_analysis_task", args=[str(source.id), str(admin.id)], queue='celery')
    return DataSourceResponse.model_validate(source)


@router.post(
    "/connect-github",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_github(
    body: Annotated[GithubConnectionRequest, Body()],
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> DataSourceResponse:
    """Connect a GitHub repository as a codebase data source."""
    
    schema_json: dict[str, Any] = {
        "source_type": "codebase", 
        "format": "github",
        "github_url": body.github_url,
        "branch": body.branch
    }
    
    # Store access token encrypted if provided
    config_encrypted = None
    if body.access_token:
        config_encrypted = encrypt_json({"access_token": body.access_token})

    source = DataSource(
        id=uuid.uuid4(),
        tenant_id=admin.tenant_id,
        type="codebase",
        name=body.name,
        schema_json=schema_json,
        config_encrypted=config_encrypted,
        indexing_status="running",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    logger.info(
        "github_repo_connected",
        tenant_id=str(admin.tenant_id),
        user_id=str(admin.id),
        source_id=str(source.id),
        github_url=body.github_url,
    )
    from app.worker import celery_app
    celery_app.send_task("process_codebase_indexing", args=[str(source.id)], queue='pillar.code')
    return DataSourceResponse.model_validate(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_data_source(
    source_id: uuid.UUID,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Delete a data source (admin only)."""
    # ── Phase 3: IAM Check ──────
    await verify_permission("delete", str(source_id), admin, db)

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
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{source_id}", response_model=DataSourceResponse)
async def get_data_source(
    source_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DataSourceResponse:
    """Get a single data source by ID."""
    await verify_permission("query", str(source_id), current_user, db)
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
    # ── Phase 3: IAM Check ──────
    await verify_permission("query", str(source_id), current_user, db)
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
