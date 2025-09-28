import requests
import logging
from bs4 import BeautifulSoup
from typing import List, Optional
from database import ForumMessage
import re
import hashlib
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RSDNScraper:
    """Scrapes RSDN forum for new messages"""
    
    def __init__(self, base_url: str = "https://rsdn.org"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def _extract_message_id_from_url(self, url: str) -> str:
        """Extract the actual message ID from RSDN URL"""
        if not url:
            return ""
        
        # Extract the message ID from URL like /forum/flame.politics.unfiltered/8998183
        import re
        match = re.search(r'/forum/[^/]+/(\d+)', url)
        if match:
            return match.group(1)
        
        # If no ID found in URL, fall back to hash (shouldn't happen with proper RSDN URLs)
        return hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
    
    def _is_recent_message(self, time_text: str) -> bool:
        """Check if message is recent (posted in minutes) - these are the ones we track"""
        return 'мин' in time_text.lower().strip()
    
    def _extract_latest_message_id_from_time_link(self, time_element) -> Optional[str]:
        """Extract the real latest message ID from the time link in main list"""
        try:
            # Time links in main list point to the actual latest message
            # Format: /forum/abroad/8998195 where 8998195 is the real message ID
            time_link = time_element.find('a')
            if time_link:
                href = time_link.get('href', '')
                match = re.search(r'/forum/[^/]+/(\d+)', href)
                if match:
                    return match.group(1)
            return None
        except Exception as e:
            logger.debug(f"Error extracting latest message ID: {e}")
            return None
    
    def _get_latest_message_content(self, thread_id: str, latest_msg_id: str) -> Optional[str]:
        """Get the latest message content using Message.aspx and timestamp correlation"""
        try:
            message_url = f"{self.base_url}/Forum/Message.aspx?mid={thread_id}"
            response = self.session.get(message_url, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find all timestamps and their associated content
            timestamp_content_map = []
            
            for time_elem in soup.find_all(string=re.compile(r'\d{2}\.\d{2}\.\d{2}\s+\d{1,2}:\d{2}')):
                time_text = time_elem.strip()
                parent = time_elem.parent
                content = ""
                
                # Search for message content near this timestamp
                for level in range(8):
                    if parent:
                        msg_divs = parent.find_all('div', class_=re.compile(r'msg|message'))
                        for div in msg_divs:
                            div_text = div.get_text(strip=True)
                            if len(div_text) > 30 and not re.match(r'^\d{2}\.\d{2}', div_text):
                                content = div_text
                                break
                        if content:
                            break
                        parent = parent.parent
                
                if content:
                    timestamp_content_map.append({
                        'time': time_text,
                        'content': content
                    })
            
            # Get the latest message by timestamp
            if timestamp_content_map:
                latest_message = max(timestamp_content_map, key=lambda x: x['time'])
                content = latest_message['content']
                
                # Clean and truncate content
                content = content.replace('\n', ' ').replace('\r', ' ').strip()
                if len(content) > 200:
                    content = content[:200].rsplit(' ', 1)[0] + "..."
                
                return content
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting latest message content for {thread_id}: {e}")
            return None
    
    def _generate_message_id(self, title: str, author: str, forum: str, time_posted: str, url: str = "", last_reply_author: str = "") -> str:
        """Generate a unique message ID - only for recent messages with minute timestamps"""
        # First try to get the thread ID from the URL
        thread_id = ""
        if url:
            rsdn_id = self._extract_message_id_from_url(url)
            if rsdn_id and rsdn_id.isdigit():
                thread_id = rsdn_id
        
        if thread_id:
            # For threads with IDs, use thread ID + last reply author
            # Don't include time - this will detect new replies but avoid minute-by-minute drift
            content = f"thread_{thread_id}|{last_reply_author or author}"
        else:
            # Fallback: use title + authors (no time to avoid drift)
            content = f"{title}|{author}|{last_reply_author or author}"
        
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        return text.strip().replace('\n', ' ').replace('\r', ' ')
    
    def _parse_time(self, time_text: str) -> str:
        """Parse and normalize time text"""
        if not time_text:
            return ""
        
        time_text = time_text.strip()
        
        # Handle Russian time formats
        if 'мин' in time_text:
            return time_text
        elif 'час' in time_text:
            return time_text
        elif 'дн' in time_text or 'дня' in time_text or 'дней' in time_text:
            return time_text
        else:
            return time_text
    
    def scrape_messages(self, max_pages: int = 1, page_size: int = 50) -> List[ForumMessage]:
        """Scrape messages from RSDN forum using the mainlist API"""
        messages = []
        
        try:
            for page in range(max_pages):
                start = page * page_size
                # Use the mainlist API endpoint that returns HTML table
                url = f"{self.base_url}/forum/mainlist/all?start={start}&pageSize={page_size}"
                
                logger.info(f"Scraping page {page + 1}: {url}")
                
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.text, 'lxml')
                page_messages = self._parse_messages(soup)
                messages.extend(page_messages)
                
                logger.info(f"Found {len(page_messages)} messages on page {page + 1}")
                
                # If we got fewer messages than requested, we've reached the end
                if len(page_messages) < page_size:
                    break
                
        except requests.RequestException as e:
            logger.error(f"Error scraping RSDN: {e}")
        except Exception as e:
            logger.error(f"Unexpected error while scraping: {e}")
        
        return messages
    
    def _parse_messages(self, soup: BeautifulSoup) -> List[ForumMessage]:
        """Parse messages from the HTML soup"""
        messages = []
        
        try:
            # The mainlist API returns a clean HTML table with class "topic-list"
            table = soup.find('table', class_='topic-list')
            
            if not table:
                logger.warning("Could not find topic-list table")
                return messages
            
            rows = table.find_all('tr')
            logger.debug(f"Found topic table with {len(rows)} rows")
            
            # Skip header row (first row)
            for row_idx, row in enumerate(rows[1:], 1):
                cells = row.find_all('td')
                
                if len(cells) < 4:  # Need at least time, forum, title, author
                    continue
                
                try:
                    # Parse the table structure from the mainlist API:
                    # 0: Time (updated)
                    # 1: Forum 
                    # 2: Subject/Title
                    # 3: Author
                    # 4: Answer count
                    # 5: Last reply author
                    # 6: Rating
                    # 7: Preview icon
                    
                    # Extract time - can be either <a> or <span>
                    time_cell = cells[0]
                    time_element = time_cell.find('a') or time_cell.find('span')
                    if time_element:
                        time_posted = self._clean_text(time_element.get_text())
                    else:
                        time_posted = self._clean_text(time_cell.get_text())
                    
                    # Only process recent messages (posted within minutes)
                    if not self._is_recent_message(time_posted):
                        logger.debug(f"Skipping old message: {time_posted}")
                        continue
                    
                    # Extract real latest message ID from time link (NEW APPROACH!)
                    latest_message_id = self._extract_latest_message_id_from_time_link(time_cell)
                    if not latest_message_id:
                        logger.debug(f"Could not extract latest message ID from time cell")
                        continue
                    
                    # Extract forum
                    forum_cell = cells[1]
                    forum_link = forum_cell.find('a')
                    if forum_link:
                        forum = self._clean_text(forum_link.get_text())
                    else:
                        forum = self._clean_text(forum_cell.get_text())
                    
                    # Extract title and URL
                    subject_cell = cells[2]
                    subject_link = subject_cell.find('a')
                    if subject_link:
                        title = self._clean_text(subject_link.get_text())
                        url = subject_link.get('href', '')
                        if url and not url.startswith('http'):
                            url = f"https://rsdn.org{url}"
                    else:
                        title = self._clean_text(subject_cell.get_text())
                        url = ""
                    
                    # Extract author
                    author_cell = cells[3]
                    author_link = author_cell.find('a')
                    if author_link:
                        author = self._clean_text(author_link.get_text())
                    else:
                        author = self._clean_text(author_cell.get_text())
                    
                    # Extract replies count
                    replies_count = 0
                    if len(cells) > 4:
                        replies_text = self._clean_text(cells[4].get_text())
                        if replies_text.isdigit():
                            replies_count = int(replies_text)
                    
                    # Extract last reply author
                    last_reply_author = None
                    if len(cells) > 5:
                        last_reply_cell = cells[5]
                        last_reply_link = last_reply_cell.find('a')
                        if last_reply_link:
                            last_reply_author = self._clean_text(last_reply_link.get_text())
                        else:
                            last_reply_text = self._clean_text(last_reply_cell.get_text())
                            if last_reply_text and last_reply_text != '-':
                                last_reply_author = last_reply_text
                    
                    # Skip invalid messages
                    if not title or not author or not forum:
                        logger.debug(f"Skipping invalid message: title='{title}', author='{author}', forum='{forum}'")
                        continue
                    
                    # Extract thread ID from the subject URL for getting message content
                    thread_id = ""
                    if url:
                        thread_match = re.search(r'/forum/[^/]+/(\d+)', url)
                        if thread_match:
                            thread_id = thread_match.group(1)
                    
                    # Get latest message content using our new method
                    latest_message_text = None
                    if thread_id and replies_count > 0:
                        latest_message_text = self._get_latest_message_content(thread_id, latest_message_id)
                    
                    # Use real message ID instead of generated hash
                    message = ForumMessage(
                        message_id=latest_message_id,  # Real RSDN message ID
                        title=title,
                        author=author,
                        forum=forum,
                        time_posted=self._parse_time(time_posted),
                        replies_count=replies_count,
                        last_reply_author=last_reply_author,
                        url=url,
                        last_message_text=latest_message_text  # Latest reply content
                    )
                    
                    messages.append(message)
                    logger.debug(f"Parsed message: {forum} - {title} by {author} (msg_id: {latest_message_id})")
                    
                    if latest_message_text:
                        logger.debug(f"Latest reply preview: {latest_message_text[:50]}...")
                    
                except Exception as e:
                    logger.debug(f"Error parsing row {row_idx}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error parsing messages: {e}")
        
        logger.info(f"Successfully parsed {len(messages)} messages")
        return messages
    
    def test_connection(self) -> bool:
        """Test connection to RSDN forum"""
        try:
            response = self.session.get(f"{self.base_url}/forum/mainlist/all?start=0&pageSize=10", timeout=10)
            response.raise_for_status()
            logger.info("Successfully connected to RSDN forum")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to RSDN forum: {e}")
            return False