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
            (2, "normalize_forum_names",
             self._migration_002_normalize_forum_names,
             "Convert ID-based forum names to human-readable names"),
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
    
    def _migration_002_normalize_forum_names(self, conn: sqlite3.Connection):
        """
        Migration 002: Normalize forum names
        Converts ID-based forum names (e.g., 'flame.politics.unfiltered') 
        to human-readable names (e.g., 'Политика (unfiltered)') based on
        production database analysis and RSDN API forum list.
        """
        cursor = conn.cursor()
        
        # Mapping based on production database analysis
        # These map URL-based forum IDs to human-readable Russian names from API
        FORUM_ID_TO_NAME = {
            'abroad': 'Заграница',
            'ai': 'Искусственный интеллект',
            'auto': 'АвтоМотоВело',
            'blockchain': 'Blockchain-технологии',
            'education': 'Образование и наука',
            'flame.comp': 'Компьютерные священные войны',
            'flame.politics': 'Политика',
            'flame.politics.unfiltered': 'Политика (unfiltered)',
            'hardware': 'Железо',
            'humour': 'Коллеги, улыбнитесь',
            'job': 'О работе',
            'life': 'О жизни',
            'philosophy': 'Философия программирования',
            'rsdn': 'Обсуждение сайта',
            'shareware': 'Shareware и бизнес',
        }
        
        # Get all current forums from database
        cursor.execute("SELECT DISTINCT forum FROM seen_messages")
        existing_forums = [row[0] for row in cursor.fetchall()]
        
        forums_to_fix = {old: new for old, new in FORUM_ID_TO_NAME.items() 
                         if old in existing_forums}
        
        if not forums_to_fix:
            logger.info("   No ID-based forum names found to normalize")
            return
        
        logger.info(f"   🔧 Normalizing {len(forums_to_fix)} forum names...")
        
        for old_name, new_name in forums_to_fix.items():
            logger.info(f"      '{old_name}' → '{new_name}'")
            
            # Update seen_messages
            cursor.execute("""
                UPDATE seen_messages 
                SET forum = ? 
                WHERE forum = ?
            """, (new_name, old_name))
            msg_count = cursor.rowcount
            
            # For chat_preferences, handle potential duplicates
            cursor.execute("""
                SELECT DISTINCT chat_id 
                FROM chat_preferences 
                WHERE preference_key = 'blocked_forum' AND preference_value = ?
            """, (old_name,))
            
            chats_with_old = [row[0] for row in cursor.fetchall()]
            pref_updated = 0
            pref_deleted = 0
            
            for chat_id in chats_with_old:
                # Check if this chat already has the new name blocked
                cursor.execute("""
                    SELECT 1 
                    FROM chat_preferences 
                    WHERE chat_id = ? AND preference_key = 'blocked_forum' AND preference_value = ?
                """, (chat_id, new_name))
                
                if cursor.fetchone():
                    # Duplicate exists - just delete the old one
                    cursor.execute("""
                        DELETE FROM chat_preferences 
                        WHERE chat_id = ? AND preference_key = 'blocked_forum' AND preference_value = ?
                    """, (chat_id, old_name))
                    pref_deleted += 1
                else:
                    # No duplicate - safe to update
                    cursor.execute("""
                        UPDATE chat_preferences 
                        SET preference_value = ? 
                        WHERE chat_id = ? AND preference_key = 'blocked_forum' AND preference_value = ?
                    """, (new_name, chat_id, old_name))
                    pref_updated += 1
            
            if pref_deleted > 0:
                logger.info(f"      ✅ {msg_count} messages, {pref_updated} prefs updated, {pref_deleted} dupes removed")
            elif pref_updated > 0:
                logger.info(f"      ✅ {msg_count} messages, {pref_updated} preferences updated")
            else:
                logger.info(f"      ✅ {msg_count} messages updated")
        
        logger.info("   ✅ Forum name normalization completed")


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
