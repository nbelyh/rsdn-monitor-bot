#!/usr/bin/env python3
"""Test the new message formatting"""

import asyncio
import logging
from scraper import RSDNScraper
from telegram_bot import TelegramNotifier
from database import DatabaseManager, ForumMessage

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_message_formatting():
    """Test the new message formatting by creating sample messages"""
    
    # Create some sample messages for testing
    sample_messages = [
        ForumMessage(
            message_id="test1",
            title="Idris 2 vs Clojure. Для чего нужен (ли) Idris 2 в индустриальном коде?",
            author="Артём",
            forum="flame.comp",
            time_posted="2 мин",
            replies_count=0,
            last_reply_author=None,
            url="https://rsdn.org/forum/flame.comp/8998184"
        ),
        ForumMessage(
            message_id="test2",
            title="Как Россия победит ВСУ",
            author="sharpcoder", 
            forum="flame.politics.unfiltered",
            time_posted="25 мин",
            replies_count=15,
            last_reply_author="Vitaliy81",
            url="https://rsdn.org/forum/flame.politics.unfiltered/8997748"
        ),
        ForumMessage(
            message_id="test3",
            title="сигареты",
            author="undo75",
            forum="abroad", 
            time_posted="31 мин",
            replies_count=3,
            last_reply_author="yoyozhik",
            url="https://rsdn.org/forum/abroad/8997795"
        )
    ]
    
    # Print formatted messages to console to see how they look
    notifier = TelegramNotifier("fake_token", "fake_chat_id")
    
    print("=== Single Message Format ===")
    for msg in sample_messages:
        formatted = notifier._format_message(msg)
        print(formatted)
        print("-" * 50)
    
    print("\n=== Multiple Messages Format ===")
    # Test what multiple messages would look like
    print("Multiple messages would be grouped and formatted together")

if __name__ == "__main__":
    asyncio.run(test_message_formatting())