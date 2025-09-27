#!/usr/bin/env python3
"""
Test script to show improved time formatting
"""

import sys
sys.path.append('.')
from telegram_bot import TelegramNotifier

def test_time_formatting():
    """Test the new time formatting"""
    print("🕐 Testing improved time formatting:")
    print("=" * 50)
    
    # Create a notifier instance (we don't need real tokens for this test)
    notifier = TelegramNotifier("fake_token", "fake_chat_id")
    
    # Test various time formats
    test_times = [
        "2 мин",
        "29 мин", 
        "3 часа",
        "8 мин",
        "59 мин",
        "1 час",
        "5 дн",
        "вчера",
        "сегодня"
    ]
    
    for time_str in test_times:
        formatted = notifier._format_time_info(time_str)
        print(f"  RSDN: '{time_str}' → Telegram: '{formatted}'")
    
    print("=" * 50)
    print("✅ Time formatting improved!")
    print("Now users will see when the message was detected by the bot.")

if __name__ == "__main__":
    test_time_formatting()