import sqlite3
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ForumMessage:
    """Represents a forum message from RSDN"""
    message_id: str  # Unique identifier (constructed from URL or similar)
    title: str
    author: str
    forum: str
    time_posted: str
    replies_count: int
    last_reply_author: Optional[str]
    url: str
    
    def __hash__(self):
        return hash(self.message_id)
    
    def __eq__(self, other):
        if isinstance(other, ForumMessage):
            return self.message_id == other.message_id
        return False

class DatabaseManager:
    """Manages SQLite database for storing seen messages"""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
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
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def is_message_seen(self, message_id: str) -> bool:
        """Check if a message has been seen before"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM seen_messages WHERE message_id = ?", 
                (message_id,)
            )
            return cursor.fetchone() is not None
    
    def add_message(self, message: ForumMessage):
        """Add a new message to the database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO seen_messages 
                (message_id, title, author, forum, time_posted, replies_count, 
                 last_reply_author, url, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                message.message_id,
                message.title,
                message.author,
                message.forum,
                message.time_posted,
                message.replies_count,
                message.last_reply_author,
                message.url
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
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE seen_messages 
                SET replies_count = ?, last_reply_author = ?, last_updated = CURRENT_TIMESTAMP
                WHERE message_id = ?
            """, (message.replies_count, message.last_reply_author, message.message_id))
            conn.commit()
    
    def cleanup_old_messages(self, days: int = 30):
        """Remove messages older than specified days"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM seen_messages 
                WHERE first_seen < datetime('now', '-{} days')
            """.format(days))
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Cleaned up {deleted} old messages")
    
    def get_stats(self) -> dict:
        """Get database statistics"""
        with sqlite3.connect(self.db_path) as conn:
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