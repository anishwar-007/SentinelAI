"""Compatibility export for the storage interface.

New code should import :class:`StorageProvider` from :mod:`sentinelai.ports`.
Concrete providers live under :mod:`sentinelai_platform.storage`.
"""

from sentinelai.ports.storage import StorageProvider

__all__ = ["StorageProvider"]
