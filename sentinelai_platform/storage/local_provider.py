import asyncio
from pathlib import Path

from sentinelai.ports.storage import StorageProvider


class LocalStorageProvider(StorageProvider):
    def __init__(self, root_dir: str = "storage") -> None:
        self._root = Path(root_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        target = (self._root / path).resolve()
        if not str(target).startswith(str(self._root.resolve())):
            raise ValueError("Invalid storage path.")
        return target

    async def upload(
        self,
        path: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> str:
        del content_type
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(target.write_bytes, data)
        return path

    async def download(self, path: str) -> bytes:
        target = self._resolve(path)
        if not target.is_file():
            raise FileNotFoundError(path)
        return await asyncio.to_thread(target.read_bytes)

    async def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target.is_file():
            await asyncio.to_thread(target.unlink)

    async def exists(self, path: str) -> bool:
        return self._resolve(path).is_file()
