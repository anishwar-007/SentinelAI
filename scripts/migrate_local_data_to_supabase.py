#!/usr/bin/env python3
"""Move local document and trace objects to Supabase Storage.

Local files are deleted only after every object has been uploaded and verified.
Trace metadata is backfilled into PostgreSQL when the trace contains a valid
execution_id that already exists in the executions table.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from uuid import UUID

from app.config import load_settings
from app.db.repositories.postgres_execution_repository import (
    PostgresExecutionRepository,
)
from app.db.repositories.postgres_trace_repository import PostgresTraceRepository
from app.db.session import create_engine, create_session_factory
from app.storage.supabase_provider import SupabaseStorageProvider
from app.tracing.persistence import TracePersister
from app.tracing.schemas import Trace

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_DIR = ROOT / "storage"
TRACES_DIR = ROOT / "traces"


async def _upload_and_verify(
    storage: SupabaseStorageProvider,
    remote_path: str,
    data: bytes,
    content_type: str,
) -> None:
    await storage.upload(remote_path, data, content_type=content_type)
    downloaded = await storage.download(remote_path)
    if downloaded != data:
        raise RuntimeError(f"Verification failed for {remote_path}")


async def main() -> None:
    settings = load_settings()
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required.")

    storage = SupabaseStorageProvider(
        settings.supabase_url,
        settings.supabase_key,
        settings.supabase_bucket,
    )
    engine = create_engine(
        settings.database_url,
        connect_args=settings.database_connect_args,
    )
    session_factory = create_session_factory(engine)
    executions = PostgresExecutionRepository(session_factory)
    traces = PostgresTraceRepository(session_factory)
    persister = TracePersister(traces, storage)

    migrated_files: list[Path] = []
    trace_metadata_count = 0

    try:
        if DOCUMENTS_DIR.is_dir():
            for local_path in sorted(path for path in DOCUMENTS_DIR.rglob("*") if path.is_file()):
                remote_path = local_path.relative_to(DOCUMENTS_DIR).as_posix()
                data = local_path.read_bytes()
                await _upload_and_verify(
                    storage,
                    remote_path,
                    data,
                    "text/plain",
                )
                migrated_files.append(local_path)
                print(f"verified {remote_path}")

        if TRACES_DIR.is_dir():
            for local_path in sorted(TRACES_DIR.glob("*.json")):
                data = local_path.read_bytes()
                trace = Trace.model_validate_json(data)
                execution_id_value = trace.metadata.get("execution_id")
                persisted_metadata = False

                if isinstance(execution_id_value, str):
                    execution_id = UUID(execution_id_value)
                    if await executions.get(execution_id) is not None:
                        if await traces.get(UUID(trace.trace_id)) is None:
                            await persister.persist(trace, execution_id)
                            trace_metadata_count += 1
                        persisted_metadata = True

                if not persisted_metadata:
                    await _upload_and_verify(
                        storage,
                        f"traces/{local_path.name}",
                        data,
                        "application/json",
                    )

                migrated_files.append(local_path)
                print(f"verified traces/{local_path.name}")

        # Delete only after the complete migration has succeeded.
        for path in migrated_files:
            path.unlink()
        for directory in (DOCUMENTS_DIR, TRACES_DIR):
            if directory.exists():
                shutil.rmtree(directory)

        print(f"migrated_objects={len(migrated_files)}")
        print(f"backfilled_trace_metadata={trace_metadata_count}")
        print("local runtime data removed")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
