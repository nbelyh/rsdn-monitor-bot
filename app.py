#!/usr/bin/env python3
"""
Azure-compatible web application entry point for RSDN Bot
"""
import os
import asyncio
import logging
from flask import Flask, jsonify, request
from threading import Thread
import signal
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import RSDNBot
from migrations import run_migrations

# Configure logging for Azure
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/rsdnbot.log', mode='a') if os.path.exists('/tmp') else logging.NullHandler()
    ]
)

logger = logging.getLogger(__name__)

# Create Flask app for Azure App Service
app = Flask(__name__)
bot_instance = None
bot_thread = None

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "RSDN Bot",
        "version": "1.0",
        "bot_running": bot_instance is not None
    })

@app.route('/status')
def status():
    """Bot status endpoint"""
    if bot_instance:
        return jsonify({
            "status": "running",
            "scheduler_running": bot_instance.scheduler.running if hasattr(bot_instance, 'scheduler') else False
        })
    else:
        return jsonify({"status": "not_running"})

@app.route('/trigger', methods=['POST'])
def manual_trigger():
    """Manual trigger endpoint for testing"""
    try:
        # Import here to avoid issues
        from main import RSDNBot
        import asyncio
        
        # Create a temporary bot instance for testing
        temp_bot = RSDNBot()
        
        # Run a single check
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(temp_bot.scan_and_notify())
            return jsonify({"status": "triggered", "result": "check completed"})
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Manual trigger error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def run_bot():
    """Run the bot in a separate thread"""
    global bot_instance
    try:
        bot_instance = RSDNBot()
        
        # Get the configured check interval from environment
        import os
        check_interval_minutes = int(os.getenv('CHECK_INTERVAL_MINUTES', '2'))
        check_interval_seconds = check_interval_minutes * 60
        logger.info(f"Flask app bot runner configured for {check_interval_minutes} minutes ({check_interval_seconds} seconds)")
        
        # For Azure App Service, we need to avoid signal handlers in threads
        # Run the bot check directly without the full scheduler
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def periodic_check():
            """Periodic check without signal handlers"""
            # Start the Telegram bot handler first
            await bot_instance.telegram_handler.start_bot()
            logger.info("Telegram bot handler started")
            
            while True:
                try:
                    await bot_instance.scan_and_notify()
                    await asyncio.sleep(check_interval_seconds)  # Use configured interval
                except Exception as e:
                    logger.error(f"Error in periodic check: {e}")
                    await asyncio.sleep(check_interval_seconds)  # Use configured interval for retry too
        
        try:
            loop.run_until_complete(periodic_check())
        except Exception as e:
            logger.error(f"Bot loop error: {e}")
        finally:
            # Cleanup
            if bot_instance and hasattr(bot_instance, 'telegram_handler'):
                loop.run_until_complete(bot_instance.telegram_handler.stop_bot())
            loop.close()
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        bot_instance = None

def start_bot_thread():
    """Start bot in background thread"""
    global bot_thread
    if bot_thread is None or not bot_thread.is_alive():
        bot_thread = Thread(target=run_bot, daemon=True)
        bot_thread.start()
        logger.info("Bot thread started")

# Auto-start bot when the module is imported
if __name__ == '__main__' or os.environ.get('WEBSITE_SITE_NAME'):
    # Run migrations first on Azure startup
    logger.info("Running database migrations on startup...")
    db_path = os.getenv('DATABASE_FILE', 'rsdn_messages.db')
    try:
        run_migrations(db_path)
        logger.info("Migrations completed successfully")
    except Exception as e:
        logger.error(f"Migration error: {e}")
    
    # Running on Azure or directly
    start_bot_thread()

# For Azure App Service
application = app

if __name__ == '__main__':
    # Local development
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)