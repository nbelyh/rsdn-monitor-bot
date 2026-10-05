import sqlite3
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

def connect_sqlite(db_path, timeout: float) -> sqlite3.Connection:
    """Open SQLite connection that is safe on Azure App Service /home (an SMB share)"""
    conn = sqlite3.connect(db_path, timeout=timeout)
    # Default DELETE journal mode removes the journal after every commit; on SMB the
    # delete can get stuck "pending", after which every write fails with "disk I/O error".
    # TRUNCATE keeps the journal file and just empties it.
    conn.execute("PRAGMA journal_mode=TRUNCATE")
    return conn

def normalize_nick(nick: str) -> str:
    """Normalize RSDN nickname for case-insensitive comparison"""
    return nick.strip().casefold()

@dataclass
class ForumMessage:
    """Represents a forum message from RSDN"""
    message_id: str  # Real RSDN message ID from latest reply
    title: str
    author: str
    forum: str
    time_posted: str
    replies_count: int
    last_reply_author: Optional[str]
    url: str
    last_message_text: Optional[str] = None  # Latest reply content for notifications
    topic_id: Optional[str] = None  # RSDN topicId ("0" for topic starters), API mode only
    parent_id: Optional[str] = None  # RSDN parentId ("0" for topic starters), API mode only

    @property
    def root_topic_id(self) -> Optional[str]:
        """ID of the topic starter message (None if unknown, e.g. in scraper mode)"""
        if self.topic_id is None:
            return None
        return self.topic_id if self.topic_id != '0' else self.message_id

    @property
    def is_new_topic(self) -> bool:
        """True if this message starts a new topic"""
        if self.parent_id is not None:
            return self.parent_id == '0'
        return self.replies_count == 0

    def __hash__(self):
        return hash(self.message_id)
    
    def __eq__(self, other):
        if isinstance(other, ForumMessage):
            return self.message_id == other.message_id
        return False

class DatabaseManager:
    """Manages SQLite database for storing seen messages"""
    
    def __init__(self, db_path: str, timeout: float, auto_migrate: bool = True):
        self.db_path = Path(db_path)
        self.timeout = timeout
        
        # Run migrations first if enabled (before init_database to handle schema changes)
        if auto_migrate:
            from migrations import MigrationManager
            migration_manager = MigrationManager(str(self.db_path), self.timeout)
            migration_manager.run_all_migrations()
        
        # Then initialize/create any missing tables
        self.init_database()
    
    def _connect(self):
        """Create a database connection with configured timeout"""
        return connect_sqlite(self.db_path, self.timeout)
    
    def init_database(self):
        """Initialize the database with required tables"""        
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_messages (
                    message_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    forum TEXT NOT NULL,
                    time_posted TEXT NOT NULL,
                    replies_count INTEGER DEFAULT 0,
                    last_reply_author TEXT,
                    url TEXT NOT NULL,
                    last_message_text TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_forum 
                ON seen_messages(forum)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_first_seen 
                ON seen_messages(first_seen)
            """)
            
            # Create chat preferences table (renamed from user_preferences for clarity)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_preferences (
                    chat_id TEXT NOT NULL,
                    preference_key TEXT NOT NULL,
                    preference_value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chat_id, preference_key, preference_value)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_prefs 
                ON chat_preferences(chat_id)
            """)

            # Topic participants (normalized author nicks per topic) for "only my topics" mode
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS topic_participants (
                    topic_id TEXT NOT NULL,
                    author TEXT NOT NULL,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (topic_id, author)
                )
            """)

            # Topics whose full participant list was loaded from RSDN API
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS loaded_topics (
                    topic_id TEXT PRIMARY KEY,
                    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            logger.info("Database initialized successfully")
    
    def is_message_seen(self, message_id: str) -> bool:
        """Check if a message has been seen before"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM seen_messages WHERE message_id = ?", 
                (message_id,)
            )
            return cursor.fetchone() is not None
    
    def add_message(self, message: ForumMessage):
        """Add a new message to the database"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO seen_messages 
                (message_id, title, author, forum, time_posted, replies_count, 
                 last_reply_author, url, last_message_text, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                message.message_id,
                message.title,
                message.author,
                message.forum,
                message.time_posted,
                message.replies_count,
                message.last_reply_author,
                message.url,
                message.last_message_text
            ))
            conn.commit()
    
    def get_new_messages(self, messages: List[ForumMessage]) -> List[ForumMessage]:
        """Filter out messages that have already been seen"""
        new_messages = []
        for message in messages:
            if not self.is_message_seen(message.message_id):
                new_messages.append(message)
                self.add_message(message)
        return new_messages
    
    def update_message_replies(self, message: ForumMessage):
        """Update reply count and last reply author for existing message"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE seen_messages 
                SET replies_count = ?, last_reply_author = ?, last_updated = CURRENT_TIMESTAMP
                WHERE message_id = ?
            """, (message.replies_count, message.last_reply_author, message.message_id))
            conn.commit()
    
    def cleanup_old_messages(self, days: int = 30):
        """Remove messages older than specified days"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM seen_messages 
                WHERE first_seen < datetime('now', '-{} days')
            """.format(days))
            deleted = cursor.rowcount

            # Drop participant data for topics without recent activity
            # (they will be reloaded from the API if they become active again)
            cursor.execute("""
                DELETE FROM topic_participants WHERE topic_id IN (
                    SELECT topic_id FROM topic_participants
                    GROUP BY topic_id
                    HAVING MAX(last_seen) < datetime('now', '-{} days')
                )
            """.format(days))
            cursor.execute("""
                DELETE FROM loaded_topics
                WHERE loaded_at < datetime('now', '-{} days')
            """.format(days))
            conn.commit()
            logger.info(f"Cleaned up {deleted} old messages")
    
    def get_recent_messages(self, hours: int = 24) -> List[ForumMessage]:
        """Get messages from the last N hours for cache optimization"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT message_id, title, author, forum, time_posted, 
                       replies_count, last_reply_author, url, last_message_text
                FROM seen_messages 
                WHERE first_seen > datetime('now', '-{} hours')
                ORDER BY first_seen DESC
            """.format(hours))
            
            messages = []
            for row in cursor.fetchall():
                message = ForumMessage(
                    message_id=row[0],
                    title=row[1],
                    author=row[2],
                    forum=row[3],
                    time_posted=row[4],
                    replies_count=row[5] or 0,
                    last_reply_author=row[6],
                    url=row[7],
                    last_message_text=row[8]
                )
                messages.append(message)
            
            return messages
    
    def get_stats(self) -> dict:
        """Get database statistics"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM seen_messages")
            total_messages = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT forum, COUNT(*) 
                FROM seen_messages 
                GROUP BY forum 
                ORDER BY COUNT(*) DESC
            """)
            forum_stats = cursor.fetchall()
            
            return {
                'total_messages': total_messages,
                'forum_stats': forum_stats
            }
    
    def get_all_forums(self) -> List[str]:
        """Get list of all forums that have messages in the database"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT forum 
                FROM seen_messages 
                ORDER BY forum
            """)
            return [row[0] for row in cursor.fetchall()]
    
    def get_chat_blocked_forums(self, chat_id: str) -> set:
        """Get list of forums blocked by chat"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT preference_value 
                FROM chat_preferences 
                WHERE chat_id = ? AND preference_key = 'blocked_forum'
            """, (chat_id,))
            
            blocked_forums = set()
            for row in cursor.fetchall():
                blocked_forums.add(row[0])
            
            return blocked_forums
    
    def block_forum_for_chat(self, chat_id: str, forum: str):
        """Block a forum for a specific chat"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO chat_preferences 
                (chat_id, preference_key, preference_value, updated_at)
                VALUES (?, 'blocked_forum', ?, CURRENT_TIMESTAMP)
            """, (chat_id, forum))
            conn.commit()
            logger.info(f"Blocked forum '{forum}' for chat {chat_id}")
    
    def unblock_forum_for_chat(self, chat_id: str, forum: str):
        """Unblock a forum for a specific chat"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM chat_preferences 
                WHERE chat_id = ? AND preference_key = 'blocked_forum' AND preference_value = ?
            """, (chat_id, forum))
            conn.commit()
            logger.info(f"Unblocked forum '{forum}' for chat {chat_id}")
    
    def reset_chat_forum_filters(self, chat_id: str):
        """Reset all forum filters for a chat"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM chat_preferences 
                WHERE chat_id = ? AND preference_key = 'blocked_forum'
            """, (chat_id,))
            deleted_count = cursor.rowcount
            conn.commit()
            logger.info(f"Reset {deleted_count} forum filters for chat {chat_id}")
            return deleted_count
    
    # Multi-chat support methods (treating each chat as a "user" for simplicity)
    def register_chat(self, chat_id: str, chat_title: str = None):
        """Register a chat for notifications"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO chat_preferences 
                (chat_id, preference_key, preference_value, updated_at)
                VALUES (?, 'registered', 'true', CURRENT_TIMESTAMP)
            """, (chat_id,))
            
            if chat_title:
                cursor.execute("""
                    INSERT OR REPLACE INTO chat_preferences 
                    (chat_id, preference_key, preference_value, updated_at)
                    VALUES (?, 'chat_title', ?, CURRENT_TIMESTAMP)
                """, (chat_id, chat_title))
            
            conn.commit()
            logger.info(f"Registered chat {chat_id} ({chat_title}) for notifications")
    
    def unregister_chat(self, chat_id: str):
        """Unregister a chat from notifications"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_preferences WHERE chat_id = ?", (chat_id,))
            conn.commit()
            logger.info(f"Unregistered chat {chat_id} from notifications")
    
    def is_chat_registered(self, chat_id: str) -> bool:
        """Check if a chat is registered for notifications"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM chat_preferences 
                WHERE chat_id = ? AND preference_key = 'registered' AND preference_value = 'true'
            """, (chat_id,))
            return cursor.fetchone() is not None
    
    def get_all_registered_chats(self) -> List[str]:
        """Get list of all registered chat IDs"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT chat_id FROM chat_preferences 
                WHERE preference_key = 'registered' AND preference_value = 'true'
                ORDER BY created_at
            """)
            return [row[0] for row in cursor.fetchall()]
    
    def get_registered_chats_count(self) -> int:
        """Get count of registered chats"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM chat_preferences 
                WHERE preference_key = 'registered' AND preference_value = 'true'
            """)
            return cursor.fetchone()[0]
    
    def increment_failed_deliveries(self, chat_id: str) -> int:
        """Increment failed delivery count for a chat and return the new count"""
        with self._connect() as conn:
            cursor = conn.cursor()
            
            # Get current count
            cursor.execute("""
                SELECT preference_value FROM chat_preferences 
                WHERE chat_id = ? AND preference_key = 'failed_deliveries'
            """, (chat_id,))
            
            result = cursor.fetchone()
            current_count = int(result[0]) if result else 0
            new_count = current_count + 1
            
            # Delete old count if exists (needed because primary key includes preference_value)
            cursor.execute("""
                DELETE FROM chat_preferences 
                WHERE chat_id = ? AND preference_key = 'failed_deliveries'
            """, (chat_id,))
            
            # Insert new count
            cursor.execute("""
                INSERT INTO chat_preferences 
                (chat_id, preference_key, preference_value, updated_at)
                VALUES (?, 'failed_deliveries', ?, CURRENT_TIMESTAMP)
            """, (chat_id, str(new_count)))
            
            conn.commit()
            logger.warning(f"Failed delivery count for chat {chat_id}: {new_count}")
            return new_count
    
    def reset_failed_deliveries(self, chat_id: str):
        """Reset failed delivery count for a chat after successful delivery"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM chat_preferences 
                WHERE chat_id = ? AND preference_key = 'failed_deliveries'
            """, (chat_id,))
            conn.commit()
    
    def get_failed_deliveries_count(self, chat_id: str) -> int:
        """Get the failed delivery count for a chat"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT preference_value FROM chat_preferences 
                WHERE chat_id = ? AND preference_key = 'failed_deliveries'
            """, (chat_id,))
            
            result = cursor.fetchone()
            return int(result[0]) if result else 0

    def _get_single_preference(self, chat_id: str, key: str) -> Optional[str]:
        """Get a single-valued chat preference"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT preference_value FROM chat_preferences
                WHERE chat_id = ? AND preference_key = ?
            """, (chat_id, key))
            result = cursor.fetchone()
            return result[0] if result else None

    def _set_single_preference(self, chat_id: str, key: str, value: Optional[str]):
        """Set (or delete, if value is None) a single-valued chat preference"""
        with self._connect() as conn:
            cursor = conn.cursor()
            # Delete old value first (needed because primary key includes preference_value)
            cursor.execute("""
                DELETE FROM chat_preferences
                WHERE chat_id = ? AND preference_key = ?
            """, (chat_id, key))
            if value is not None:
                cursor.execute("""
                    INSERT INTO chat_preferences
                    (chat_id, preference_key, preference_value, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (chat_id, key, value))
            conn.commit()

    def get_chat_rsdn_nick(self, chat_id: str) -> Optional[str]:
        """Get RSDN nickname linked to a chat"""
        return self._get_single_preference(chat_id, 'rsdn_nick')

    def set_chat_rsdn_nick(self, chat_id: str, nick: Optional[str]):
        """Link RSDN nickname to a chat (None to unlink)"""
        self._set_single_preference(chat_id, 'rsdn_nick', nick)
        logger.info(f"Set RSDN nick for chat {chat_id}: {nick}")

    def is_own_topics_mode(self, chat_id: str) -> bool:
        """Check if chat wants only new topics and replies in topics it participated in"""
        return self._get_single_preference(chat_id, 'own_topics_only') == 'true'

    def set_own_topics_mode(self, chat_id: str, enabled: bool):
        """Enable/disable "only my topics" mode for a chat"""
        self._set_single_preference(chat_id, 'own_topics_only', 'true' if enabled else None)
        logger.info(f"Own topics mode for chat {chat_id}: {enabled}")

    def has_own_topics_mode_chats(self) -> bool:
        """Check if any registered chat uses "only my topics" mode"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM chat_preferences
                WHERE preference_key = 'own_topics_only' AND preference_value = 'true'
                LIMIT 1
            """)
            return cursor.fetchone() is not None

    def add_topic_participants(self, participants: List[Tuple[str, str]]):
        """Record (topic_id, author_nick) pairs"""
        rows = [(topic_id, normalize_nick(nick)) for topic_id, nick in participants if topic_id and nick]
        if not rows:
            return
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO topic_participants (topic_id, author, last_seen)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(topic_id, author) DO UPDATE SET last_seen = CURRENT_TIMESTAMP
            """, rows)
            conn.commit()

    def is_topic_participant(self, topic_id: str, nick: str) -> bool:
        """Check if the given nick has posted in the topic"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM topic_participants
                WHERE topic_id = ? AND author = ?
            """, (topic_id, normalize_nick(nick)))
            return cursor.fetchone() is not None

    def get_unloaded_topics(self, topic_ids: List[str]) -> List[str]:
        """Return topic IDs whose full participant list hasn't been loaded yet"""
        with self._connect() as conn:
            cursor = conn.cursor()
            unloaded = []
            for topic_id in dict.fromkeys(topic_ids):
                cursor.execute("SELECT 1 FROM loaded_topics WHERE topic_id = ?", (topic_id,))
                if cursor.fetchone() is None:
                    unloaded.append(topic_id)
            return unloaded

    def mark_topics_loaded(self, topic_ids: List[str]):
        """Mark topics as having their full participant list loaded"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO loaded_topics (topic_id, loaded_at)
                VALUES (?, CURRENT_TIMESTAMP)
            """, [(topic_id,) for topic_id in topic_ids])
            conn.commit()