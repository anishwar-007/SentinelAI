#!/usr/bin/env python3
"""Index sample documents into the reference runtime."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples" / "documents"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"


async def main() -> None:
    base_url = DEFAULT_BASE_URL.rstrip("/")
    files = sorted(SAMPLES_DIR.glob("*.txt"))
    if not files:
        raise SystemExit(f"No sample documents found in {SAMPLES_DIR}")

    async with httpx.AsyncClient(timeout=120.0) as client:
        for path in files:
            content = path.read_text(encoding="utf-8")
            response = await client.post(
                f"{base_url}/documents",
                json={
                    "content": content,
                    "filename": path.name,
                    "source": str(path),
                },
            )
            response.raise_for_status()
            payload = response.json()
            print(f"Indexed {path.name} -> {payload.get('document_id')}")


if __name__ == "__main__":
    asyncio.run(main())
