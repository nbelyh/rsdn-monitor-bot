import os
import logging
import asyncio
import signal
from pathlib import Path
from typing import Set, Optional, List
from datetime import datetime

# Configure logging first
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database import DatabaseManager, ForumMessage
from scraper import RSDNScraper
from telegram_bot import TelegramNotifier, TelegramBotHandler

# Load environment variables
load_dotenv()

class RSDNBot:
    """Main bot class that coordinates scraping and notifications"""
    
    def __init__(self):
        self.setup_logging()
        self.load_config()
        
        # Initialize components
        self.db = DatabaseManager(self.database_file)
        self.scraper = RSDNScraper(self.rsdn_url, db_manager=self.db)
        self.telegram_notifier = TelegramNotifier(self.bot_token, self.chat_id, self.db)
        self.telegram_handler = TelegramBotHandler(self.bot_token, self.chat_id, self.db)
        
        # Scheduler for periodic tasks
        self.scheduler = AsyncIOScheduler()
        
        # Runtime state
        self.running = False
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        log_file = os.getenv('LOG_FILE', 'rsdn_bot.log')
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        # Set third-party loggers to WARNING to reduce noise
        logging.getLogger('telegram').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('apscheduler').setLevel(logging.WARNING)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Logging initialized")
    
    def load_config(self):
        """Load configuration from environment variables"""
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.scan_interval = int(os.getenv('SCAN_INTERVAL_SECONDS', '60'))
        self.rsdn_url = os.getenv('RSDN_URL', 'https://rsdn.org')
        self.database_file = os.getenv('DATABASE_FILE', 'rsdn_messages.db')
        
        # Parse monitored forums
        monitored_forums_str = os.getenv('MONITORED_FORUMS', '')
        if monitored_forums_str.strip():
            self.monitored_forums = set(
                forum.strip() for forum in monitored_forums_str.split(',')
                if forum.strip()
            )
        else:
            self.monitored_forums = None
        
        # Validate required configuration
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is required")
        
        self.logger.info("Configuration loaded successfully")
        if self.monitored_forums:
            self.logger.info(f"Monitoring forums: {', '.join(self.monitored_forums)}")
        else:
            self.logger.info("Monitoring all forums")
    
    async def scan_and_notify(self):
        """Scan for new messages and send notifications"""
        try:
            self.logger.info("Starting scan for new messages...")
            
            # Scrape messages from RSDN
            messages = self.scraper.scrape_messages(max_pages=1)
            self.logger.info(f"Scraped {len(messages)} total messages")
            
            if not messages:
                self.logger.warning("No messages found during scraping")
                return
            
            # Get only new messages
            new_messages = self.db.get_new_messages(messages)
            self.logger.info(f"Found {len(new_messages)} new messages")
            
            if new_messages:
                # Send notifications
                await self.telegram_notifier.send_new_messages(
                    new_messages, 
                    self.monitored_forums
                )
                
                self.logger.info(f"Sent notifications for {len(new_messages)} new messages")
            
        except Exception as e:
            self.logger.error(f"Error during scan and notify: {e}")
            try:
                await self.telegram_notifier.send_status_message(
                    f"❌ Ошибка при сканировании: {str(e)}"
                )
            except:
                pass
    
    async def test_connections(self) -> bool:
        """Test all external connections"""
        self.logger.info("Testing connections...")
        
        # Test RSDN connection
        if not self.scraper.test_connection():
            self.logger.error("RSDN connection test failed")
            return False
        
        # Test Telegram connection
        if not await self.telegram_notifier.test_connection():
            self.logger.error("Telegram connection test failed")
            return False
        
        self.logger.info("All connections tested successfully")
        return True
    
    def setup_scheduler(self):
        """Setup the periodic task scheduler"""
        self.scheduler.add_job(
            self.scan_and_notify,
            IntervalTrigger(seconds=self.scan_interval),
            id='scan_rsdn',
            name='Scan RSDN for new messages',
            max_instances=1,
            coalesce=True
        )
        
        # Add cleanup job (run daily at 2 AM)
        self.scheduler.add_job(
            lambda: self.db.cleanup_old_messages(days=30),
            'cron',
            hour=2,
            minute=0,
            id='cleanup_old_messages',
            name='Cleanup old messages'
        )
        
        self.logger.info(f"Scheduler configured with {self.scan_interval}s interval")
    
    async def start(self):
        """Start the bot"""
        self.logger.info("Starting RSDN Bot...")
        
        try:
            # Test connections
            if not await self.test_connections():
                raise Exception("Connection tests failed")
            
            # Start Telegram bot handler
            await self.telegram_handler.start_bot()
            
            # Send startup notification
            await self.telegram_notifier.send_status_message(
                "🤖 <b>RSDN Bot запущен!</b>\n\n"
                f"⏰ Интервал сканирования: {self.scan_interval} секунд\n"
                f"📂 Отслеживаемые форумы: {'все' if not self.monitored_forums else ', '.join(self.monitored_forums)}"
            )
            
            # Setup and start scheduler
            self.setup_scheduler()
            self.scheduler.start()
            
            # Run initial scan
            await self.scan_and_notify()
            
            self.running = True
            self.logger.info("RSDN Bot started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start bot: {e}")
            raise
    
    async def stop(self):
        """Stop the bot gracefully"""
        self.logger.info("Stopping RSDN Bot...")
        
        self.running = False
        
        try:
            # Stop scheduler
            if self.scheduler.running:
                self.scheduler.shutdown()
            
            # Send shutdown notification
            await self.telegram_notifier.send_status_message(
                "🛑 <b>RSDN Bot остановлен</b>"
            )
            
            # Stop Telegram bot
            await self.telegram_handler.stop_bot()
            
            self.logger.info("RSDN Bot stopped gracefully")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
    
    async def run(self):
        """Run the bot with proper signal handling"""
        # Setup signal handlers
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            await self.start()
            
            # Keep the bot running
            while self.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
        finally:
            await self.stop()

async def main():
    """Main entry point"""
    try:
        bot = RSDNBot()
        await bot.run()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    asyncio.run(main())