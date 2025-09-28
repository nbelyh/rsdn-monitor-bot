#!/usr/bin/env python3
"""
Database migration script to wipe old database and create new schema
Run this once to migrate from user_preferences to chat_preferences
"""

import os
from pathlib import Path

def migrate_database():
    """Remove old database and create fresh one with new schema"""
    db_path = Path('rsdn_messages.db')
    
    print(f"🗄️  Database Migration Script")
    print(f"=" * 40)
    
    if db_path.exists():
        print(f"📁 Found existing database: {db_path}")
        print(f"🗑️  Removing old database...")
        os.remove(db_path)
        print(f"✅ Old database removed")
    else:
        print(f"📁 No existing database found")
    
    print(f"🔧 Creating new database with updated schema...")
    
    # Import and initialize the new database
    from database import DatabaseManager
    db = DatabaseManager(str(db_path))
    
    print(f"✅ New database created with chat_preferences table")
    print(f"")
    print(f"📋 New Schema:")
    print(f"  - seen_messages (unchanged)")
    print(f"  - chat_preferences (was: user_preferences)")
    print(f"    - chat_id (was: user_id)")
    print(f"    - preference_key")  
    print(f"    - preference_value")
    print(f"")
    print(f"🎯 Next Steps:")
    print(f"  1. Start the bot: python main.py")
    print(f"  2. Users send /start to register their chats")
    print(f"  3. Bot will send notifications to all registered chats")
    print(f"")
    print(f"✨ Migration completed successfully!")

if __name__ == "__main__":
    migrate_database()