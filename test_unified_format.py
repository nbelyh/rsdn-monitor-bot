#!/usr/bin/env python3
"""Test the new unified message format"""

import asyncio
import os
from telegram_bot import TelegramNotifier
from database import DatabaseManager

# Mock ForumMessage class for testing
class MockForumMessage:
    def __init__(self, title, author, forum, url, time_posted, replies_count=0, last_reply_author=None):
        self.title = title
        self.author = author
        self.forum = forum
        self.url = url
        self.time_posted = time_posted
        self.replies_count = replies_count
        self.last_reply_author = last_reply_author

async def test_unified_format():
    """Test the new unified message format"""
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in .env")
        return
    
    # Initialize components
    db = DatabaseManager('rsdn_messages.db')
    notifier = TelegramNotifier(BOT_TOKEN, CHAT_ID, db)
    
    print("🧪 Testing unified message format...")
    
    # Test single message (should still have timestamp and filter button)
    single_message = MockForumMessage(
        title="Тест единичного сообщения",
        author="TestUser1",
        forum="Test Forum",
        url="https://rsdn.org/forum/test/12345",
        time_posted="14:30",
        replies_count=5,
        last_reply_author="LastUser"
    )
    
    # Test multiple messages (should have timestamps and filter button)
    multiple_messages = [
        MockForumMessage(
            title="Первое тестовое сообщение",
            author="TestUser2", 
            forum="Test Forum",
            url="https://rsdn.org/forum/test/12346",
            time_posted="14:25",
            replies_count=2,
            last_reply_author="ReplyUser1"
        ),
        MockForumMessage(
            title="Второе тестовое сообщение",
            author="TestUser3",
            forum="Test Forum", 
            url="https://rsdn.org/forum/test/12347",
            time_posted="14:20",
            replies_count=0
        )
    ]
    
    print("📤 Sending test single message...")
    await notifier.send_new_messages([single_message])
    
    print("📤 Sending test multiple messages...")
    await notifier.send_new_messages(multiple_messages)
    
    print("✅ Test messages sent! Check your Telegram chat.")
    print("📋 Both messages should now have:")
    print("   • 🕐 Timestamps visible")
    print("   • 🚫 Filter buttons")
    print("   • 👤 Author information")
    print("   • 💬 Reply counts")

if __name__ == "__main__":
    asyncio.run(test_unified_format())