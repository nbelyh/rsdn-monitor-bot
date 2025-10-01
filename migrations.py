"""
Database migration system for RSDN Bot
Automatically applies migrations in order based on version tracking.
"""
import sqlite3
import logging
from pathlib import Path
from typing import List, Callable, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database schema migrations"""
    
    def __init__(self, db_path: str, timeout: float):
        self.db_path = Path(db_path)
        self.timeout = timeout
        self._ensure_migrations_table()
    
    def _connect(self):
        """Create a database connection with configured timeout"""
        return sqlite3.connect(self.db_path, timeout=self.timeout)
    
    def _ensure_migrations_table(self):
        """Create migrations tracking table if it doesn't exist"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            """)
            conn.commit()
    
    def get_current_version(self) -> int:
        """Get the current database schema version"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(version) FROM schema_migrations")
            result = cursor.fetchone()[0]
            return result if result is not None else 0
    
    def is_migration_applied(self, version: int) -> bool:
        """Check if a specific migration version has been applied"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?",
                (version,)
            )
            return cursor.fetchone() is not None
    
    def record_migration(self, version: int, name: str, description: str = ""):
        """Record that a migration has been applied"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO schema_migrations (version, name, description)
                VALUES (?, ?, ?)
            """, (version, name, description))
            conn.commit()
            logger.info(f"✅ Migration {version} ({name}) applied successfully")
    
    def apply_migration(self, version: int, name: str, 
                       migration_func: Callable[[sqlite3.Connection], None],
                       description: str = ""):
        """Apply a single migration if not already applied"""
        if self.is_migration_applied(version):
            logger.info(f"⏭️  Migration {version} ({name}) already applied, skipping")
            return False
        
        logger.info(f"🔧 Applying migration {version}: {name}")
        logger.info(f"   Description: {description}")
        
        try:
            with self._connect() as conn:
                # Execute the migration
                migration_func(conn)
                conn.commit()
                
            # Record successful migration
            self.record_migration(version, name, description)
            return True
            
        except Exception as e:
            logger.error(f"❌ Migration {version} ({name}) failed: {e}")
            raise
    
    def run_all_migrations(self):
        """Run all defined migrations in order"""
        current_version = self.get_current_version()
        logger.info(f"📊 Current database schema version: {current_version}")
        
        migrations = self.get_migrations()
        applied_count = 0
        
        for version, name, migration_func, description in migrations:
            if version > current_version:
                if self.apply_migration(version, name, migration_func, description):
                    applied_count += 1
        
        if applied_count > 0:
            new_version = self.get_current_version()
            logger.info(f"✅ Applied {applied_count} migration(s). Schema version: {current_version} → {new_version}")
        else:
            logger.info("✅ Database schema is up to date")
    
    def get_migrations(self) -> List[Tuple[int, str, Callable, str]]:
        """
        Define all migrations in order.
        Returns: List of (version, name, migration_function, description)
        """
        return [
            (1, "fix_chat_preferences_pk", 
             self._migration_001_fix_chat_preferences,
             "Fix PRIMARY KEY to allow multiple blocked forums per chat"),
        ]
    
    # ==================== Individual Migration Functions ====================
    
    def _migration_001_fix_chat_preferences(self, conn: sqlite3.Connection):
        """
        Migration 001: Fix chat_preferences PRIMARY KEY
        Changes PRIMARY KEY from (chat_id, preference_key) 
        to (chat_id, preference_key, preference_value)
        to allow multiple blocked forums per chat.
        """
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='chat_preferences'
        """)
        if not cursor.fetchone():
            logger.info("   chat_preferences table doesn't exist yet, skipping migration")
            return
        
        # Check current schema to see if migration is needed
        cursor.execute("PRAGMA table_info(chat_preferences)")
        columns = cursor.fetchall()
        
        # Get primary key info
        cursor.execute("PRAGMA index_list(chat_preferences)")
        indexes = cursor.fetchall()
        
        # Backup existing data
        logger.info("   📦 Backing up existing data...")
        cursor.execute("SELECT chat_id, preference_key, preference_value FROM chat_preferences")
        existing_data = cursor.fetchall()
        logger.info(f"   Found {len(existing_data)} existing records")
        
        # Drop old table
        logger.info("   🗑️  Dropping old table...")
        cursor.execute("DROP TABLE chat_preferences")
        
        # Create new table with correct PRIMARY KEY
        logger.info("   🏗️  Creating new table with updated schema...")
        cursor.execute("""
            CREATE TABLE chat_preferences (
                chat_id TEXT NOT NULL,
                preference_key TEXT NOT NULL,
                preference_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, preference_key, preference_value)
            )
        """)
        
        # Recreate index
        cursor.execute("""
            CREATE INDEX idx_chat_prefs 
            ON chat_preferences(chat_id)
        """)
        
        # Restore data
        if existing_data:
            logger.info(f"   ♻️  Restoring {len(existing_data)} records...")
            cursor.executemany("""
                INSERT OR IGNORE INTO chat_preferences 
                (chat_id, preference_key, preference_value)
                VALUES (?, ?, ?)
            """, existing_data)
        
        logger.info("   ✅ Schema migration completed")


def run_migrations(db_path: str, timeout: float):
    """
    Convenience function to run all pending migrations.
    Safe to call on every application startup.
    """
    logger.info("🚀 Starting database migration check...")
    manager = MigrationManager(db_path, timeout=timeout)
    manager.run_all_migrations()
    logger.info("🎉 Migration check complete")


if __name__ == '__main__':
    # Allow running migrations manually
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    run_migrations('rsdn_messages.db', timeout=5.0)
