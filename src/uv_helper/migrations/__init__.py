"""Database migration system for UV-Helper state."""

from .base import CURRENT_SCHEMA_VERSION, Migration
from .migration_001_add_source_type import Migration001AddSourceType
from .migration_002_add_copy_parent_dir import Migration002AddCopyParentDir
from .runner import MigrationRunner

# Registry of all migrations in order
MIGRATIONS: list[Migration] = [
    Migration001AddSourceType(),
    Migration002AddCopyParentDir(),
]

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "Migration",
    "Migration001AddSourceType",
    "Migration002AddCopyParentDir",
    "MigrationRunner",
    "MIGRATIONS",
]
