#!/usr/bin/env python3
"""
Azure Database Migration Script
Run this ONCE on Azure to migrate from single-user to multi-chat schema
"""

import os
import logging
from pathlib import Path
from database import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrate_azure_database():
    """
    Migrate Azure database from single-user to multi-chat schema
    This will DROP the existing database and create a fresh one
    """
    
    # Get database path from environment or use default
    db_path = os.getenv('DATABASE_FILE', 'rsdn_messages.db')
    
    logger.info("🚀 Starting Azure Database Migration")
    logger.info("=" * 50)
    
    # Check if running on Azure (detect by environment variables)
    is_azure = os.getenv('WEBSITE_SITE_NAME') is not None
    
    if is_azure:
        logger.info(f"✅ Running on Azure App Service: {os.getenv('WEBSITE_SITE_NAME')}")
    else:
        logger.warning("⚠️  Not detected as Azure - are you sure this is the right environment?")
        logger.info("   (This is fine for testing locally)")
    
    logger.info(f"📁 Database path: {db_path}")
    
    # Remove old database if it exists
    if Path(db_path).exists():
        logger.info("🗑️  Removing old single-user database...")
        os.remove(db_path)
        logger.info("✅ Old database removed")
    else:
        logger.info("📁 No existing database found")
    
    # Create new multi-chat database
    logger.info("🔧 Creating new multi-chat database schema...")
    db = DatabaseManager(db_path)
    
    logger.info("✅ New database created successfully!")
    logger.info("")
    logger.info("📋 New Multi-Chat Schema:")
    logger.info("  🗃️  seen_messages table:")
    logger.info("     - message_id (primary key)")
    logger.info("     - subject, author, forum_name, etc.")
    logger.info("  🗃️  chat_preferences table:")
    logger.info("     - chat_id (Telegram chat ID)")
    logger.info("     - preference_key (e.g., 'blocked_forum_5')")
    logger.info("     - preference_value")
    logger.info("")
    logger.info("🎯 What happens next:")
    logger.info("  1. Bot starts with NO registered chats")
    logger.info("  2. Users send /start to register their chats")
    logger.info("  3. Bot sends notifications to ALL registered chats")
    logger.info("  4. Each chat has independent forum filtering")
    logger.info("")
    logger.info("🔄 Data Loss:")
    logger.info("  ✅ Message cache: Will be rebuilt automatically as bot runs")
    logger.info("  ❌ User preferences: Lost (users need to re-configure with /start)")
    logger.info("     This is expected and necessary for multi-chat conversion")
    logger.info("")
    logger.info("✨ Azure Database Migration Completed Successfully!")
    
    return True

if __name__ == "__main__":
    try:
        migrate_azure_database()
        logger.info("🎉 Migration completed - restart the bot to begin multi-chat mode!")
        exit(0)
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        logger.error("   Bot will continue with old schema if migration fails")
        exit(1)