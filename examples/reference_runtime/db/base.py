"""Document models share the SentinelAI SQLAlchemy Base for one DB upgrade path."""

from sentinelai_platform.persistence.postgres.base import Base

__all__ = ["Base"]
