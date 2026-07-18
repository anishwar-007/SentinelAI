from abc import ABC, abstractmethod


class StorageProvider(ABC):
    @abstractmethod
    async def upload(self, path: str, data: bytes, *, content_type: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    async def download(self, path: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def exists(self, path: str) -> bool:
        raise NotImplementedError
