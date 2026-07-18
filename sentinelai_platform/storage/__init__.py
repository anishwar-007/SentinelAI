"""Concrete object-storage providers for SentinelAI Platform."""

from sentinelai_platform.storage.local_provider import LocalStorageProvider
from sentinelai_platform.storage.supabase_provider import SupabaseStorageProvider

__all__ = ["LocalStorageProvider", "SupabaseStorageProvider"]
