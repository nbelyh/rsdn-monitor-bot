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
from rsdn_api_client import RSDNAPIClient
from telegram_bot import TelegramNotifier, TelegramBotHandler
from migrations import run_migrations

# Load environment variables
load_dotenv()

class RSDNBot:
    """Main bot class that coordinates scraping and notifications"""
    
    def __init__(self):
        self.setup_logging()
        self.load_config()
        
        # Run database migrations before initializing components
        self.logger.info("Checking for database migrations...")
        run_migrations(self.database_file, timeout=self.database_timeout)
        
        # Initialize components
        self.db = DatabaseManager(self.database_file, timeout=self.database_timeout)
        
        # Choose between API client and HTML scraper
        if self.use_api_client:
            self.logger.info("Using RSDN SOAP API client")
            self.scraper = RSDNAPIClient(
                username=self.rsdn_username,
                password=self.rsdn_password,
                base_url=self.rsdn_url,
                db_manager=self.db
            )
        else:
            self.logger.info("Using HTML scraper (legacy mode)")
            self.scraper = RSDNScraper(self.rsdn_url, db_manager=self.db)
        
        self.telegram_notifier = TelegramNotifier(self.bot_token, self.db)
        self.telegram_handler = TelegramBotHandler(self.bot_token, self.db, self.scan_interval_minutes)
        
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
        
        # API client toggle
        self.use_api_client = os.getenv('USE_API_CLIENT', 'false').lower() == 'true'
        
        # RSDN API credentials (required if USE_API_CLIENT=true)
        self.rsdn_username = os.getenv('RSDN_USERNAME', '')
        self.rsdn_password = os.getenv('RSDN_PASSWORD', '')
        
        # Get check interval in minutes (convert to seconds for internal use)
        check_interval_minutes = int(os.getenv('CHECK_INTERVAL_MINUTES', '1'))
        self.scan_interval = check_interval_minutes * 60  # Convert to seconds for scheduler
        self.scan_interval_minutes = check_interval_minutes  # Keep original minutes for display
            
        self.rsdn_url = os.getenv('RSDN_URL', 'https://rsdn.org')
        self.database_file = os.getenv('DATABASE_FILE', 'rsdn_messages.db')
        self.database_timeout = float(os.getenv('DATABASE_TIMEOUT', '5.0'))
        
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
        
        # Validate API credentials if API mode is enabled
        if self.use_api_client:
            if not self.rsdn_username or not self.rsdn_password:
                raise ValueError(
                    "RSDN_USERNAME and RSDN_PASSWORD are required when USE_API_CLIENT=true"
                )
        
        # Note: TELEGRAM_CHAT_ID is no longer required - users register via /start
        
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
            
            # Send startup notification to all registered chats
            registered_chats = self.db.get_all_registered_chats()
            if registered_chats:
                await self.telegram_notifier.send_status_message(
                    "🤖 <b>RSDN Bot запущен!</b>\n\n"
                    f"⏰ Интервал сканирования: {self.scan_interval_minutes} мин\n"
                    f"📂 Отслеживаемые форумы: {'все' if not self.monitored_forums else ', '.join(self.monitored_forums)}\n"
                    f"👥 Зарегистрированных чатов: {len(registered_chats)}"
                )
                self.logger.info(f"Sent startup notification to {len(registered_chats)} chats")
            else:
                self.logger.info("No registered chats found - use /start to register for notifications")
            
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