import asyncio

from storage3.types import FileOptions
from supabase import Client, create_client

from sentinelai.ports.storage import StorageProvider


class SupabaseStorageProvider(StorageProvider):
    def __init__(self, url: str, key: str, bucket: str) -> None:
        self._client: Client = create_client(url, key)
        self._bucket = bucket

    async def upload(
        self,
        path: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> str:
        file_options: FileOptions = {"upsert": "true"}
        if content_type:
            file_options["content-type"] = content_type

        def _upload() -> None:
            self._client.storage.from_(self._bucket).upload(
                path,
                data,
                file_options=file_options,
            )

        await asyncio.to_thread(_upload)
        return path

    async def download(self, path: str) -> bytes:
        def _download() -> bytes:
            return self._client.storage.from_(self._bucket).download(path)

        return await asyncio.to_thread(_download)

    async def delete(self, path: str) -> None:
        def _delete() -> None:
            self._client.storage.from_(self._bucket).remove([path])

        await asyncio.to_thread(_delete)

    async def exists(self, path: str) -> bool:
        directory = str(_path_parent(path))
        name = path.rsplit("/", 1)[-1]

        def _exists() -> bool:
            entries = self._client.storage.from_(self._bucket).list(directory)
            return any(item.get("name") == name for item in entries)

        return await asyncio.to_thread(_exists)


def _path_parent(path: str) -> str:
    if "/" not in path:
        return ""
    return path.rsplit("/", 1)[0]
