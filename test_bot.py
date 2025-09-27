#!/usr/bin/env python3
"""
RSDN Forum Bot Test Runner
Tests the bot components individually before running the main application.
"""

import asyncio
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_scraper():
    """Test the RSDN scraper functionality"""
    print("🔍 Testing RSDN Scraper...")
    
    try:
        from scraper import RSDNScraper
        
        scraper = RSDNScraper()
        
        # Test connection
        if not scraper.test_connection():
            print("❌ RSDN connection failed")
            return False
        
        # Test scraping
        messages = scraper.scrape_messages(max_pages=1)
        print(f"✅ Successfully scraped {len(messages)} messages")
        
        # Show some sample messages
        if messages:
            print(f"\n📝 Sample messages:")
            for i, msg in enumerate(messages[:3], 1):
                print(f"  {i}. {msg.forum} - {msg.title} by {msg.author}")
        
        return True
        
    except Exception as e:
        print(f"❌ Scraper test failed: {e}")
        return False

async def test_database():
    """Test database functionality"""
    print("\n🗃️  Testing Database...")
    
    try:
        from database import DatabaseManager, ForumMessage
        
        # Use test database
        db = DatabaseManager("test_rsdn.db")
        
        # Create test message
        test_message = ForumMessage(
            message_id="test_123",
            title="Test Message",
            author="Test Author",
            forum="test",
            time_posted="1 мин",
            replies_count=5,
            last_reply_author="Last Author",
            url="https://test.url"
        )
        
        # Test adding message
        db.add_message(test_message)
        
        # Test checking if message is seen
        is_seen = db.is_message_seen("test_123")
        if not is_seen:
            print("❌ Message should be seen after adding")
            return False
        
        # Test getting stats
        stats = db.get_stats()
        print(f"✅ Database working. Total messages: {stats['total_messages']}")
        
        # Clean up test database
        Path("test_rsdn.db").unlink(missing_ok=True)
        
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

async def test_telegram():
    """Test Telegram bot functionality"""
    print("\n📱 Testing Telegram Bot...")
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in .env file")
        return False
    
    try:
        from telegram_bot import TelegramNotifier
        
        notifier = TelegramNotifier(bot_token, chat_id)
        
        # Test connection
        if not await notifier.test_connection():
            print("❌ Telegram connection failed")
            return False
        
        # Send test message
        await notifier.send_status_message("🧪 <b>Test message from RSDN Bot</b>\n\nTelegram connection is working!")
        
        print("✅ Telegram test successful - check your chat for test message")
        return True
        
    except Exception as e:
        print(f"❌ Telegram test failed: {e}")
        return False

async def test_configuration():
    """Test configuration loading"""
    print("\n⚙️  Testing Configuration...")
    
    try:
        # Check required environment variables
        required_vars = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
            print("   Please check your .env file")
            return False
        
        # Check optional variables
        scan_interval = int(os.getenv('SCAN_INTERVAL_SECONDS', '60'))
        monitored_forums = os.getenv('MONITORED_FORUMS', '')
        
        print(f"✅ Configuration loaded successfully:")
        print(f"   Scan interval: {scan_interval} seconds")
        print(f"   Monitored forums: {'all' if not monitored_forums.strip() else monitored_forums}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

async def run_integration_test():
    """Run a full integration test"""
    print("\n🔄 Running Integration Test...")
    
    try:
        from database import DatabaseManager
        from scraper import RSDNScraper
        from telegram_bot import TelegramNotifier
        
        # Initialize components
        db = DatabaseManager("test_integration.db")
        scraper = RSDNScraper()
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        notifier = TelegramNotifier(bot_token, chat_id)
        
        # Scrape some messages
        print("  Scraping messages...")
        messages = scraper.scrape_messages(max_pages=1)
        
        if not messages:
            print("❌ No messages found during integration test")
            return False
        
        # Check for new messages (first run, so all should be new)
        print("  Checking for new messages...")
        new_messages = db.get_new_messages(messages[:3])  # Test with first 3 messages
        
        print(f"  Found {len(new_messages)} new messages")
        
        # Send notification
        if new_messages:
            print("  Sending test notification...")
            await notifier.send_status_message(
                f"🧪 <b>Integration Test</b>\n\n"
                f"Found {len(new_messages)} messages in integration test.\n"
                f"Sample: {new_messages[0].title} in {new_messages[0].forum}"
            )
        
        print("✅ Integration test completed successfully")
        
        # Clean up test database
        Path("test_integration.db").unlink(missing_ok=True)
        
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🧪 RSDN Bot Test Suite")
    print("=" * 50)
    
    tests = [
        ("Configuration", test_configuration),
        ("Database", test_database),
        ("Scraper", test_scraper),
        ("Telegram", test_telegram),
        ("Integration", run_integration_test)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = await test_func()
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n📈 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The bot is ready to run.")
        print("💡 Run 'python main.py' to start the bot.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the configuration and dependencies.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))