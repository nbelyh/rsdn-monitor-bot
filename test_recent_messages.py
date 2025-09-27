#!/usr/bin/env python3
"""Test the recent message filtering logic"""

import logging
from scraper import RSDNScraper

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_recent_messages():
    """Test the scraper with recent message filtering"""
    scraper = RSDNScraper()
    
    # Test connection
    if not scraper.test_connection():
        logger.error("Failed to connect to RSDN")
        return
    
    # Scrape messages (will only get recent ones with minutes)
    logger.info("Scraping recent messages (minutes only)...")
    messages = scraper.scrape_messages(max_pages=1, page_size=50)
    
    logger.info(f"Found {len(messages)} recent messages")
    
    # Show the messages we found
    for msg in messages[:10]:  # Show first 10
        print(f"[{msg.forum}] {msg.title}")
        print(f"  Author: {msg.author}")
        print(f"  Time: {msg.time_posted}")
        if msg.last_reply_author:
            print(f"  Last reply: {msg.last_reply_author}")
        print(f"  ID: {msg.message_id}")
        print(f"  URL: {msg.url}")
        print()

if __name__ == "__main__":
    test_recent_messages()