"""Base classes for database migrations."""

from abc import ABC, abstractmethod

from tinydb import TinyDB

# Current schema version - increment when adding new migrations.
# This should match the highest version number in the MIGRATIONS list.
CURRENT_SCHEMA_VERSION = 2


class Migration(ABC):
    """Base class for database migrations."""

    version: int

    @abstractmethod
    def migrate(self, db: TinyDB) -> None:
        """
        Perform the migration on the database.

        Args:
            db: TinyDB database instance
        """
        pass

    @abstractmethod
    def description(self) -> str:
        """Return a human-readable description of this migration."""
        pass
