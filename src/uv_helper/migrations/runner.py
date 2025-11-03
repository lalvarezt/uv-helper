"""Migration runner for database schema updates."""

from rich.console import Console
from tinydb import TinyDB

from .base import CURRENT_SCHEMA_VERSION, Migration

console = Console()


class MigrationRunner:
    """Runs database migrations."""

    def __init__(self, db: TinyDB):
        """
        Initialize migration runner.

        Args:
            db: TinyDB database instance
        """
        self.db = db
        # Metadata table stores schema version as a single document with doc_id=1.
        # Using a fixed doc_id ensures we always retrieve/update the same document
        # instead of creating multiple version entries.
        self.metadata = db.table("metadata")

    def get_schema_version(self) -> int:
        """
        Get current schema version from database.

        Returns:
            Current schema version, or 0 if not set
        """
        result = self.metadata.get(doc_id=1)
        if result and isinstance(result, dict):
            return result.get("schema_version", 0)
        return 0

    def set_schema_version(self, version: int) -> None:
        """
        Set schema version in database.

        Args:
            version: Schema version to set
        """
        # Use update if doc exists, otherwise insert
        if self.metadata.get(doc_id=1):
            self.metadata.update({"schema_version": version}, doc_ids=[1])
        else:
            self.metadata.insert({"schema_version": version})

    def needs_migration(self) -> bool:
        """
        Check if any migrations need to be run.

        Returns:
            True if migrations are pending
        """
        current_version = self.get_schema_version()
        return current_version < CURRENT_SCHEMA_VERSION

    def run_migrations(self, migrations: list[Migration]) -> None:
        """
        Run all pending migrations.

        Args:
            migrations: List of migrations to run
        """
        current_version = self.get_schema_version()

        if current_version >= CURRENT_SCHEMA_VERSION:
            # Already at latest version
            return

        console.print(
            f"Running database migrations (v{current_version} -> v{CURRENT_SCHEMA_VERSION})..."
        )

        # Run each migration that hasn't been applied yet
        for migration in migrations:
            if migration.version > current_version:
                try:
                    console.print(
                        f"  Applying migration {migration.version}: {migration.description()}"
                    )
                    migration.migrate(self.db)
                    self.set_schema_version(migration.version)
                except Exception as e:
                    console.print(f"[red]Error:[/red] Migration {migration.version} failed: {e}")
                    console.print(
                        "[yellow]Hint:[/yellow] Consider backing up your state file "
                        "before retrying."
                    )
                    raise

        console.print("Database migrations completed.")
