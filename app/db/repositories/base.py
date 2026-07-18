from abc import ABC, abstractmethod
from uuid import UUID


class Repository[T](ABC):
    @abstractmethod
    async def get(self, entity_id: UUID) -> T | None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, entity_id: UUID) -> None:
        raise NotImplementedError
