"""
RSDN SOAP API Client
Uses official RSDN JanusAT web service for forum synchronization
"""

import logging
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import base64

# Import ForumMessage from database module
from database import ForumMessage
from text_cleaner import clean_message_text

logger = logging.getLogger(__name__)

# RSDN API returns message dates in Moscow time (UTC+3, no DST since 2014)
RSDN_UTC_OFFSET = timedelta(hours=3)


class RSDNAPIClient:
    """
    RSDN JanusAT SOAP API Client
    
    Uses official RSDN web service instead of HTML scraping.
    Requires authenticated RSDN account credentials.
    """
    
    def __init__(self, username: str, password: str, base_url: str = "https://rsdn.org", db_manager=None):
        """
        Initialize API client with credentials
        
        Args:
            username: RSDN account username
            password: RSDN account password
            base_url: RSDN base URL (default: https://rsdn.org)
            db_manager: Optional database manager for state persistence
        """
        if not username or not password:
            raise ValueError("RSDN_USERNAME and RSDN_PASSWORD are required for API access")
        
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/ws/janusAT.asmx"
        self.db_manager = db_manager
        
        # SOAP namespace
        self.ns = {
            'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
            'janus': 'http://rsdn.ru/Janus/'
        }
        
        # Row version tracking (for incremental sync)
        self.message_row_version = "AAAAAAAAAAA="  # Initial value
        self.rating_row_version = "AAAAAAAAAAA="
        self.moderate_row_version = "AAAAAAAAAAA="
        
        # Track if we've done first sync (for isFirstRequest flag)
        self._first_sync_done = False
        
        # Forum ID to name mapping cache
        self._forum_map: Dict[int, str] = {}
        
        # Session for HTTP requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RSDN-Monitor/1.0 (Python)',  # rsdn.org returns 403 for UAs containing "bot"
            'Content-Type': 'text/xml; charset=utf-8',
            'Accept-Encoding': 'gzip, deflate'
        })
        
        # Load row versions from database if available
        if self.db_manager:
            self._load_row_versions()
        
        logger.info(f"RSDN API client initialized for user: {username}")
    
    def _load_row_versions(self):
        """Load row versions from database for incremental sync"""
        try:
            # TODO: Implement database storage for row versions
            # For now, using default values
            pass
        except Exception as e:
            logger.debug(f"Could not load row versions: {e}")
    
    def _save_row_versions(self):
        """Save row versions to database"""
        try:
            # TODO: Implement database storage for row versions
            pass
        except Exception as e:
            logger.debug(f"Could not save row versions: {e}")
    
    def _build_soap_envelope(self, method: str, body_content: str) -> str:
        """Build SOAP envelope for API request"""
        return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" 
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    <{method} xmlns="http://rsdn.ru/Janus/">
{body_content}
    </{method}>
  </soap:Body>
</soap:Envelope>"""
    
    def _make_soap_request(self, method: str, body_content: str) -> ET.Element:
        """
        Make SOAP request to RSDN API
        
        Args:
            method: SOAP method name (e.g., 'GetNewData')
            body_content: XML content for method parameters
            
        Returns:
            Parsed XML response root element
        """
        soap_envelope = self._build_soap_envelope(method, body_content)
        
        headers = {
            'SOAPAction': f'"http://rsdn.ru/Janus/{method}"'
        }
        
        try:
            response = self.session.post(
                self.api_url,
                data=soap_envelope.encode('utf-8'),
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            # Parse XML response
            root = ET.fromstring(response.content)
            return root
            
        except requests.exceptions.RequestException as e:
            logger.error(f"SOAP request failed for {method}: {e}")
            raise
        except ET.ParseError as e:
            logger.error(f"Failed to parse SOAP response: {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test API connectivity (alias for check_connection)
        Compatible with RSDNScraper interface
        
        Returns:
            True if API is accessible, False otherwise
        """
        return self.check_connection()
    
    def check_connection(self) -> bool:
        """
        Test API connectivity using Check method
        
        Returns:
            True if API is accessible, False otherwise
        """
        try:
            logger.info("Testing RSDN API connectivity...")
            root = self._make_soap_request('Check', '')
            logger.info("✅ RSDN API connection successful")
            return True
        except Exception as e:
            logger.error(f"❌ RSDN API connection failed: {e}")
            return False
    
    def get_forum_list(self) -> Dict[int, str]:
        """
        Get list of all forums with ID to name mapping
        
        Returns:
            Dictionary mapping forum_id (int) to forum_name (str)
        """
        logger.info("Fetching forum list from API...")
        
        body = f"""      <forumRequest>
        <userName>{self.username}</userName>
        <password>{self.password}</password>
        <forumsRowVersion>AAAAAAAAAAA=</forumsRowVersion>
      </forumRequest>"""
        
        try:
            root = self._make_soap_request('GetForumList', body)
            
            # Parse forum list
            forum_map = {}
            for forum in root.findall('.//janus:JanusForumInfo', self.ns):
                forum_id = int(forum.find('janus:forumId', self.ns).text)
                forum_name = forum.find('janus:forumName', self.ns).text
                forum_map[forum_id] = forum_name
            
            self._forum_map = forum_map
            logger.info(f"✅ Retrieved {len(forum_map)} forums")
            return forum_map
            
        except Exception as e:
            logger.error(f"Failed to fetch forum list: {e}")
            return {}
    
    def get_new_messages(self, forum_ids: Optional[List[int]] = None, minutes: int = 5) -> List[ForumMessage]:
        """
        Get new messages from subscribed forums
        
        Args:
            forum_ids: Optional list of forum IDs to fetch (None = all forums)
            minutes: Look for messages posted in last N minutes (for filtering)
            
        Returns:
            List of ForumMessage objects
        """
        logger.info("Fetching new messages from API...")
        
        # Ensure forum map is loaded
        if not self._forum_map:
            self.get_forum_list()
        
        # Build subscribed forums list
        # If no specific forums requested, subscribe to ALL forums
        if forum_ids is None:
            forum_ids = list(self._forum_map.keys())
            logger.debug(f"Subscribing to all {len(forum_ids)} forums")
        
        # Determine if this is first request (for incremental sync)
        # Use true only on very first sync, then false for incremental updates
        is_first_request = "true" if not self._first_sync_done else "false"
        
        if forum_ids:
            forums_xml = '\n'.join([
                f"""          <RequestForumInfo>
            <forumId>{fid}</forumId>
            <isFirstRequest>{is_first_request}</isFirstRequest>
          </RequestForumInfo>"""
                for fid in forum_ids
            ])
            subscribed_forums = f"""        <subscribedForums>
{forums_xml}
        </subscribedForums>"""
        else:
            # Fallback - no forums (shouldn't happen now)
            subscribed_forums = "        <subscribedForums />"
        
        body = f"""      <changeRequest>
        <userName>{self.username}</userName>
        <password>{self.password}</password>
{subscribed_forums}
        <ratingRowVersion>{self.rating_row_version}</ratingRowVersion>
        <messageRowVersion>{self.message_row_version}</messageRowVersion>
        <moderateRowVersion>{self.moderate_row_version}</moderateRowVersion>
        <breakMsgIds />
        <breakTopicIds />
        <maxOutput>0</maxOutput>
      </changeRequest>"""
        
        try:
            root = self._make_soap_request('GetNewData', body)
            
            # Update row versions for next sync
            self._update_row_versions(root)
            
            # Mark first sync as complete (for incremental updates)
            if not self._first_sync_done:
                self._first_sync_done = True
                logger.debug("First sync completed - subsequent calls will be incremental")
            
            # Parse messages
            messages = self._parse_messages(root, minutes)
            
            logger.info(f"✅ Retrieved {len(messages)} new messages")
            return messages
            
        except Exception as e:
            logger.error(f"Failed to fetch new messages: {e}")
            return []
    
    def _update_row_versions(self, root: ET.Element):
        """Update row versions from API response"""
        try:
            result = root.find('.//janus:GetNewDataResult', self.ns)
            if result is not None:
                rating_rv = result.find('janus:lastRatingRowVersion', self.ns)
                message_rv = result.find('janus:lastForumRowVersion', self.ns)
                moderate_rv = result.find('janus:lastModerateRowVersion', self.ns)
                
                if rating_rv is not None and rating_rv.text:
                    self.rating_row_version = rating_rv.text
                if message_rv is not None and message_rv.text:
                    self.message_row_version = message_rv.text
                if moderate_rv is not None and moderate_rv.text:
                    self.moderate_row_version = moderate_rv.text
                
                self._save_row_versions()
                logger.debug(f"Updated row versions: msg={self.message_row_version[:10]}...")
        except Exception as e:
            logger.debug(f"Could not update row versions: {e}")
    
    def _parse_messages(self, root: ET.Element, recent_minutes: int) -> List[ForumMessage]:
        """Parse messages from GetNewData response"""
        messages = []
        current_time = datetime.utcnow()
        
        # Ensure forum map is loaded
        if not self._forum_map:
            self.get_forum_list()
        
        # Count total messages in response (before filtering)
        all_messages = root.findall('.//janus:JanusMessageInfo', self.ns)
        logger.debug(f"API returned {len(all_messages)} total messages in response")
        
        filtered_count = 0

        # Record topic participants from all messages (including old ones filtered below)
        self._record_participants(all_messages)

        for msg in all_messages:
            try:
                # Extract message fields
                message_id = msg.find('janus:messageId', self.ns).text
                topic_id = msg.find('janus:topicId', self.ns).text
                parent_id = msg.find('janus:parentId', self.ns).text
                forum_id = int(msg.find('janus:forumId', self.ns).text)
                subject = msg.find('janus:subject', self.ns).text or "Без темы"
                user_nick = msg.find('janus:userNick', self.ns).text or "Аноним"
                message_text = msg.find('janus:message', self.ns).text or ""
                message_date_str = msg.find('janus:messageDate', self.ns).text
                
                # Parse message date
                message_date = self._parse_datetime(message_date_str)
                
                # Filter by time (only recent messages)
                time_diff = (current_time - message_date).total_seconds() / 60
                
                logger.debug(f"Message {message_id}: posted {time_diff:.1f} minutes ago (limit: {recent_minutes})")
                
                if time_diff > recent_minutes:
                    filtered_count += 1
                    continue
                
                # Get forum name
                forum_name = self._forum_map.get(forum_id, f"Forum {forum_id}")
                
                # Clean message content (remove HTML, truncate)
                content = self._clean_message_content(message_text)
                
                # Format time
                time_posted = f"{int(time_diff)} мин"
                
                # Build message URL
                url = f"{self.base_url}/forum/message/{message_id}"
                
                # Create ForumMessage object (matching database.py structure)
                forum_message = ForumMessage(
                    message_id=message_id,
                    title=subject,
                    author=user_nick,
                    forum=forum_name,  # Use 'forum' not 'forum_name'
                    time_posted=time_posted,
                    replies_count=0,  # Not directly available in single message
                    last_reply_author=user_nick,
                    url=url,
                    last_message_text=content,  # Use 'last_message_text' not 'content'
                    topic_id=topic_id,
                    parent_id=parent_id
                )
                
                messages.append(forum_message)
                
            except Exception as e:
                logger.debug(f"Failed to parse message: {e}")
                continue
        
        logger.debug(f"Filtered out {filtered_count} messages older than {recent_minutes} minutes")
        logger.debug(f"Returning {len(messages)} recent messages")

        return messages

    def _extract_participants(self, messages: List[ET.Element]) -> List[Tuple[str, str]]:
        """Extract (root_topic_id, author_nick) pairs from JanusMessageInfo elements"""
        participants = []
        for msg in messages:
            try:
                message_id = msg.find('janus:messageId', self.ns).text
                topic_id = msg.find('janus:topicId', self.ns).text
                user_nick = msg.find('janus:userNick', self.ns).text
                if user_nick:
                    root_topic_id = topic_id if topic_id != '0' else message_id
                    participants.append((root_topic_id, user_nick))
            except Exception as e:
                logger.debug(f"Failed to extract participant: {e}")
        return participants

    def _record_participants(self, messages: List[ET.Element]):
        """Save topic participants to database"""
        if not self.db_manager:
            return
        try:
            self.db_manager.add_topic_participants(self._extract_participants(messages))
        except Exception as e:
            logger.error(f"Failed to record topic participants: {e}")

    def load_topic_participants(self, topic_ids: List[str]) -> List[str]:
        """
        Load full participant lists for topics via GetTopicByMessage

        Args:
            topic_ids: Root message IDs of topics to load

        Returns:
            List of topic IDs that were loaded successfully
        """
        if not topic_ids or not self.db_manager:
            return []

        ids_xml = ''.join(f"<int>{tid}</int>" for tid in topic_ids)
        body = f"""      <topicRequest>
        <userName>{self.username}</userName>
        <password>{self.password}</password>
        <messageIds>{ids_xml}</messageIds>
      </topicRequest>"""

        try:
            root = self._make_soap_request('GetTopicByMessage', body)
            participants = self._extract_participants(root.findall('.//janus:JanusMessageInfo', self.ns))
            self.db_manager.add_topic_participants(participants)

            loaded = [tid for tid in topic_ids if any(p[0] == tid for p in participants)]
            self.db_manager.mark_topics_loaded(loaded)
            logger.info(f"Loaded participants for {len(loaded)}/{len(topic_ids)} topics")
            return loaded

        except Exception as e:
            logger.error(f"Failed to load topic participants: {e}")
            return []

    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse datetime from SOAP response (ISO 8601 format, Moscow time) into naive UTC"""
        try:
            # Handle format: 2025-09-30T14:23:45.123
            if '.' in dt_str:
                dt_str = dt_str.split('.')[0]  # Remove microseconds
            return datetime.fromisoformat(dt_str.replace('Z', '')) - RSDN_UTC_OFFSET
        except Exception as e:
            logger.debug(f"Failed to parse datetime '{dt_str}': {e}")
            return datetime.utcnow()
    
    def _clean_message_content(self, text: str) -> str:
        """Clean and truncate message content"""
        return clean_message_text(text, max_length=200)
    
    def scrape_messages(self, max_pages: int = 1, page_size: int = 50) -> List[ForumMessage]:
        """
        Main entry point - compatible with RSDNScraper interface
        
        Args:
            max_pages: Ignored (API uses incremental sync)
            page_size: Ignored (API returns all new messages)
            
        Returns:
            List of new ForumMessage objects
        """
        # Get recent messages (last 5 minutes by default)
        return self.get_new_messages(minutes=5)
