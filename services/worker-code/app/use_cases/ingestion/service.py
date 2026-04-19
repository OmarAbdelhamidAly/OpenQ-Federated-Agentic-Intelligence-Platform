import os
import shutil
import structlog
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.infrastructure.code_extractor import CodeExtractor
from app.infrastructure.neo4j_adapter import Neo4jAdapter
from app.infrastructure.ast_parser import ASTParser
from app.infrastructure.code_store import CodeStore
from app.use_cases.ingestion.enricher import CodeEnricher
from app.infrastructure.config import settings
from app.modules.code.utils.taxonomy import DEFAULT_EXCLUSIONS

logger = structlog.get_logger(__name__)

async def run_codebase_ingestion(source_id: str) -> None:
    """
    Strategic Use-case orchestrator for Codebase Ingestion.
    Implements Hierarchical (Bottom-Up) Enrichment.
    """
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    root_dir: str | None = None

    try:
        # ── 1. Fetch source metadata ───────────────────────────────────
        async with async_session() as session:
            row = (await session.execute(
                text("SELECT tenant_id, schema_json, file_path FROM data_sources WHERE id = :id"),
                {"id": source_id},
            )).fetchone()

        if not row:
            logger.error("ingestion_source_not_found", source_id=source_id)
            return

        tenant_id, schema_json, file_path = row
        schema_json = schema_json or {}

        # ── 2. Extract / clone codebase ────────────────────────────────
        root_dir = CodeExtractor.extract_or_clone(
            tenant_id=str(tenant_id),
            source_id=source_id,
            file_path=file_path,
            github_url=schema_json.get("github_url"),
            branch=schema_json.get("branch", "main"),
            access_token=schema_json.get("access_token"),
        )
        logger.info("ingestion_codebase_extracted", source_id=source_id, root_dir=root_dir)

        # ── 3. Wipe stale data ─────────────────────────────────────────
        adapter = Neo4jAdapter()
        await adapter.delete_source_graph(source_id)
        CodeStore().delete_all(source_id)

        # ── 4. Tiered Scanning ─────────────────────────────────────────
        parser = ASTParser()
        enricher = CodeEnricher()
        semaphore = asyncio.Semaphore(15) # Concurrency control for LLM calls

        all_dirs:     list[dict] = []
        all_files:    list[dict] = []
        all_entities: list[dict] = []
        all_imports:  list[dict] = []
        all_calls:    list[dict] = []

        # Data map for hierarchical summarization
        file_summaries_map = {} # path -> summary
        dir_files_map = {}      # dir_path -> [file_summaries]

        for subdir, _dirs, files in os.walk(root_dir):
            rel_subdir = os.path.relpath(subdir, root_dir).replace("\\", "/")
            if rel_subdir == ".": rel_subdir = ""
            
            # Skip excluded directories
            if any(exc in rel_subdir.split("/") for exc in DEFAULT_EXCLUSIONS):
                continue

            all_dirs.append({"path": rel_subdir, "name": os.path.basename(subdir) or "root"})

            for filename in files:
                full_path = os.path.join(subdir, filename)
                rel_path  = os.path.relpath(full_path, root_dir).replace("\\", "/")
                ext       = os.path.splitext(filename)[1]
                
                # Metadata for Neo4j
                all_files.append({"path": rel_path, "name": filename, "ext": ext, "dir_path": rel_subdir})

                # AST parse and collect entities
                file_entities = []
                for node in parser.parse_file(full_path):
                    if node["type"] in ["Class", "Function"]:
                        node["file_path"] = rel_path
                        file_entities.append(node)
                    elif node["type"] == "Import":
                        all_imports.append({"file_path": rel_path, "name": node["name"]})
                    elif node["type"] == "Call":
                        all_calls.append({
                            "file_path": rel_path,
                            "name": node["name"],
                            "caller_name": node.get("caller_name", "global")
                        })
                
                # Enqueue for enrichment
                all_entities.extend(file_entities)

        # ── 5. Hierarchical Enrichment (Bottom-Up) ───────────────────
        
        # Step A: Summarize Entities (Functions/Classes)
        async def enrich_entity(e):
            async with semaphore:
                enrichment_data = await enricher.semantic_summarize(e.get("code", ""))
                e["summary"] = enrichment_data.get("summary", "Unknown")
                e["semantic_archetype"] = enrichment_data.get("semantic_archetype", "Unknown")
                e["inferred_domain"] = enrichment_data.get("inferred_domain", "Unknown")
                e["execution_nature"] = enrichment_data.get("execution_nature", "Unknown")
                e["architectural_layer"] = enrichment_data.get("architectural_layer", "Unknown")
                e["structural_health"] = enrichment_data.get("structural_health", "Unknown")
                
                if e["summary"] and enricher.embeddings_model:
                     e["embedding"] = await enricher.embed(e["summary"])
            # Remove giant code blocks before Neo4j
            e.pop("code", None)

        logger.info("enriching_entities", count=len(all_entities))
        await asyncio.gather(*(enrich_entity(e) for e in all_entities))

        # Step B: Summarize Files Based on Entities
        logger.info("enriching_files", count=len(all_files))
        async def enrich_file(f):
            f_path = f["path"]
            f_entities = [e for e in all_entities if e["file_path"] == f_path]
            entity_summaries = [e["summary"] for e in f_entities if e.get("summary")]
            
            async with semaphore:
                f["summary"] = await enricher.summarize_file(entity_summaries)
            
            file_summaries_map[f_path] = f["summary"]
            # Track for directory enrichment
            d_path = f["dir_path"]
            if d_path not in dir_files_map: dir_files_map[d_path] = []
            dir_files_map[d_path].append(f["summary"])

        await asyncio.gather(*(enrich_file(f) for f in all_files))

        # Step C: Summarize Directories Based on Files
        logger.info("enriching_directories", count=len(all_dirs))
        async def enrich_directory(d):
            d_path = d["path"]
            f_summaries = dir_files_map.get(d_path, [])
            async with semaphore:
                enrichment = await enricher.summarize_directory(f_summaries, d["name"])
                d["summary"] = enrichment.get("summary")
                d["domain"] = enrichment.get("domain")

        await asyncio.gather(*(enrich_directory(d) for d in all_dirs))

        # ── 6. Batch-write Strategic Graph ──────────────────────────
        await adapter.batch_build_tree(source_id, all_dirs, all_files)
        await adapter.batch_upsert_entities(source_id, all_entities)
        await adapter.batch_upsert_file_metadata(source_id, all_files)
        await adapter.batch_upsert_directory_metadata(source_id, all_dirs)
        await adapter.batch_upsert_dependencies(source_id, all_imports)
        await adapter.batch_upsert_calls(source_id, all_calls)
        await adapter.execute_nexus_bridge(source_id)

        # ── 7. Finalize Status ───────────────────────────────────────
        async with async_session() as session:
            await session.execute(
                text("UPDATE data_sources SET indexing_status = 'done', last_error = NULL WHERE id = :id"),
                {"id": source_id},
            )
            await session.commit()

        logger.info("strategic_ingestion_complete", source_id=source_id)

    except Exception as exc:
        logger.error("strategic_ingestion_failed", error=str(exc))
        async with async_session() as session:
            await session.execute(
                text("UPDATE data_sources SET indexing_status = 'failed', last_error = :err WHERE id = :id"),
                {"id": source_id, "err": str(exc)},
            )
            await session.commit()

    finally:
        if root_dir and os.path.exists(root_dir):
            shutil.rmtree(root_dir)
        await engine.dispose()
