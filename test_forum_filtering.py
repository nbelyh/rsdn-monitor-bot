#!/usr/bin/env python3
"""Test the new forum filtering functionality"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from telegram_bot import TelegramBotHandler, TelegramNotifier
from database import DatabaseManager

load_dotenv()

async def test_forum_filtering():
    """Test the forum filtering commands and functionality"""
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Get environment variables
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print('❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in .env')
        return
    
    # Initialize components
    db = DatabaseManager('rsdn_messages.db')
    bot_handler = TelegramBotHandler(bot_token, chat_id, db)
    
    try:
        print('🚀 Starting bot with forum filtering...')
        await bot_handler.start_bot()
        
        print('✅ Bot started successfully!')
        print('📱 New commands available:')
        print('   /start - Show welcome with filtering info')
        print('   /filters - Show current blocked forums')
        print('   /reset_filters - Reset all filters')
        print('   🚫 Button on messages to block forums')
        print()
        print('💡 Try:')
        print('   1. Send /start to see new welcome message')
        print('   2. Send /filters to see current filters')
        print('   3. Click "🚫 Не показывать..." on a message')
        print('   4. Send /filters again to see the blocked forum')
        print('   5. Send /reset_filters to clear all filters')
        print()
        print('⏳ Bot will run for 90 seconds...')
        
        # Keep the bot running for 90 seconds to test
        await asyncio.sleep(90)
        
        print('⏹️ Stopping bot...')
        await bot_handler.stop_bot()
        print('✅ Bot stopped')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_forum_filtering())