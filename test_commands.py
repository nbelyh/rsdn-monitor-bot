#!/usr/bin/env python3
"""Test the telegram bot commands"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from telegram_bot import TelegramBotHandler
from database import DatabaseManager

load_dotenv()

async def test_commands():
    """Test the bot commands functionality"""
    
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
        print('🚀 Starting bot with command handlers...')
        await bot_handler.start_bot()
        
        print('✅ Bot started successfully!')
        print('📱 Bot is now listening for commands:')
        print('   /start - Show welcome message')
        print('   /status - Show bot status')  
        print('   /stats - Show detailed statistics')
        print()
        print('💡 Go to your Telegram and try sending /start to your bot')
        print('⏳ Bot will run for 60 seconds then stop...')
        
        # Keep the bot running for 60 seconds to test commands
        await asyncio.sleep(60)
        
        print('⏹️ Stopping bot...')
        await bot_handler.stop_bot()
        print('✅ Bot stopped')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_commands())