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
    if bot_instance:
        try:
            # This would trigger a manual run
            asyncio.create_task(bot_instance.check_and_notify())
            return jsonify({"status": "triggered"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "bot_not_running"}), 500

def run_bot():
    """Run the bot in a separate thread"""
    global bot_instance
    try:
        bot_instance = RSDNBot()
        
        # Run the bot
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(bot_instance.run())
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        finally:
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
    # Running on Azure or directly
    start_bot_thread()

# For Azure App Service
application = app

if __name__ == '__main__':
    # Local development
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)