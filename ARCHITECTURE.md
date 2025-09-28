# RSDN Forum Monitor Bot - Architecture & Design Document

## Project Overview
A multi-user Telegram bot that monitors the RSDN (Russian Software Developer Network) forum for new messages and sends real-time notifications to registered chats. Deployed on Azure App Service F1 (free tier) with traffic optimization achieving 98% bandwidth reduction.

**Key Features**: Multi-chat support, per-chat forum filtering, dynamic user registration via `/start` command.

## Architecture Components

### Core Modules
1. **main.py** - Entry point and orchestration
2. **scraper.py** - Forum scraping with traffic optimization
3. **telegram_bot.py** - Telegram notifications and user interaction
4. **database.py** - SQLite data persistence and caching
5. **app.py** - Flask wrapper for Azure App Service compatibility

### Key Features
- **Multi-chat support** - Any user/group/channel can register with `/start`
- **Per-chat forum filtering** - Independent preferences for each registered chat
- **Real-time monitoring** of RSDN forum mainlist
- **Smart traffic optimization** with caching (98% bandwidth reduction)
- **Message deduplication** using real RSDN message IDs
- **User-friendly Telegram interface** with inline buttons
- **Content preview** extraction from messages
- **Zero-reply message support** (fixed critical parsing issue)

## Technical Architecture

### Deployment Platform
- **Azure App Service** F1 (free tier, Linux)
- **Runtime**: Python 3.11 with Gunicorn WSGI server
- **Region**: West Europe
- **Git deployment** from local repository

### Data Flow
```
RSDN Forum -> Scraper -> Database Cache -> Telegram Bot -> All Registered Chats
```

### Traffic Optimization Strategy
1. **Mainlist caching** - 5-minute cache for forum main page
2. **Message content caching** - Permanent cache for already processed messages
3. **Processed message tracking** - Avoid re-fetching known messages
4. **Adaptive page sizing** - Reduce page size when cache hit ratio > 80%

### Message Processing Pipeline
1. **Fetch mainlist** from `https://rsdn.org/forum/mainlist/all`
2. **Parse HTML table** to extract message metadata
3. **Filter recent messages** (posted within minutes using "мин" detection)
4. **Extract message IDs** from subject links (not time links - critical fix)
5. **Fetch content** for new messages with caching
6. **Send notifications** to all registered chats with per-chat forum filtering

### Recent Message Detection ("мин" Filtering)
**Core Logic**: Only process messages posted within minutes (not hours/days)
```python
def _is_recent_message(self, time_text: str) -> bool:
    """Check if message is recent (posted in minutes) - these are the ones we track"""
    time_lower = time_text.lower().strip()
    return 'мин' in time_lower
```

**Time Format Examples**:
- ✅ "23 мин" - Recent, will be processed
- ✅ "45 мин назад" - Recent, will be processed  
- ❌ "1 час" - Old, will be skipped
- ❌ "2 часа" - Old, will be skipped
- ❌ "1 день" - Old, will be skipped

**Rationale**: 
- RSDN shows relative timestamps for recent posts
- Minutes indicate very fresh content worth immediate notification
- Hours/days indicate older content users likely already saw
- Reduces noise and focuses on truly new activity

## Critical Fixes Implemented

### 1. Zero-Reply Message Parsing Issue
**Problem**: Bot parsed 0 messages when recent messages had 0 replies
**Root Cause**: Message ID extraction from time cells (which don't have links)
**Solution**: Extract message IDs from subject links instead
```python
# Before (broken)
latest_message_id = self._extract_latest_message_id_from_time_link(time_cell)

# After (fixed)
subject_link = subject_cell.find('a')
if subject_link:
    href = subject_link.get('href', '')
    match = re.search(r'/forum/[^/]+/(\d+)', href)
    if match:
        latest_message_id = match.group(1)
```

### 2. Content Retrieval Logic
**Enhancement**: Ensure content is fetched for messages with 0 replies
```python
# Get content for both messages with and without replies
if thread_id and latest_message_id:
    latest_message_text = self._get_latest_message_content(thread_id, latest_message_id)
```

### 3. Reply Count Handling & Message Content Strategy
**Critical Issue**: Different logic needed for messages with 0 replies vs messages with replies

**For Messages with 0 Replies** (New Topics):
- `message_id` = Original thread starter message ID from subject link
- `author` = Original topic creator (thread starter)
- `content` = Content of the original message
- `last_reply_author` = None or empty
- URL points to the original message

**For Messages with 1+ Replies** (Active Threads):
- `message_id` = Still uses original thread ID (limitation of current parsing)
- `author` = Latest reply author (if available)
- `content` = Content from latest reply in the thread
- `last_reply_author` = Author of most recent reply
- URL points to latest message in thread

**Implementation Logic**:
```python
# Author selection logic
author = last_reply_author if (replies_count > 0 and last_reply_author) else author

# Content fetching (same method, but _get_latest_message_content handles the logic)
if thread_id and latest_message_id:
    latest_message_text = self._get_latest_message_content(thread_id, latest_message_id)
```

**Why This Matters**:
- Zero-reply topics are often the most interesting (new discussions starting)
- Previous bug caused bot to ignore all zero-reply messages completely
- Users expect to see both new topics AND replies to existing topics
- Different presentation makes sense: new topics show original author, replies show latest contributor

### 6. Multi-Chat Architecture Conversion
**Major Enhancement**: Converted from single-user to multi-chat bot

**Registration System**:
```python
# Users register their chats dynamically
@self.application.add_handler(CommandHandler("start", self.start_command))
@self.application.add_handler(CommandHandler("stop", self.stop_command))

# Notifications sent to all registered chats
registered_chats = self.db_manager.get_all_registered_chats()
for chat_id in registered_chats:
    # Send notification with per-chat forum filtering
```

**Benefits**:
- No hardcoded `TELEGRAM_CHAT_ID` configuration required
- Anyone can use the bot by sending `/start`
- Each chat maintains independent forum filtering preferences
- Supports personal chats, group chats, and channels
- Scalable to unlimited users without configuration changes

### 4. Author Attribution Logic
**Fix**: Show original author for messages without replies
```python
author=last_reply_author if (replies_count > 0 and last_reply_author) else author
```

### 5. Emoji Display Issue
**Problem**: Broken emoji character in Telegram messages
**Solution**: Replace corrupted character with proper 👤 emoji

## Configuration Management

### Environment Variables
- `TELEGRAM_BOT_TOKEN` - Bot authentication
- `RSDN_URL` - Forum base URL (https://rsdn.org)
- `CHECK_INTERVAL_MINUTES` - Polling frequency (default: 5)
- `DATABASE_PATH` - SQLite database location

### Dynamic Configuration
- Users can filter forums via inline Telegram buttons
- Scan interval display adapts to configured value
- Forum blocking persists in database

## Database Schema

### Tables
1. **seen_messages** - Processed message cache and deduplication
2. **chat_preferences** - Per-chat settings and forum filtering

### Key Fields
**seen_messages table**:
- `message_id` - Real RSDN message ID (not hash)
- `last_message_text` - Cached content preview
- `replies_count` - Thread reply count
- `time_posted` - Formatted timestamp

**chat_preferences table**:
- `chat_id` - Telegram chat ID (users, groups, channels)
- `preference_key` - Setting name (e.g., 'blocked_forum_5')
- `preference_value` - Setting value

## Telegram Bot Interface

### Commands
- `/start` - Register chat for notifications and show help
- `/stop` - Unregister chat from notifications
- `/status` - Show bot status and configuration
- `/forums` - List available forums with blocking options
- `/block_forum <id>` - Block specific forum in this chat
- `/unblock_forum <id>` - Unblock specific forum in this chat
- `/help` - Display command list

### Message Format
```
📝 forum_name

• [Message Title](link)
  👤 author • 🕐 time • 💬 X replies
  "Content preview..."

🚫 Don't show messages from forum_name
```

### Inline Features
- Forum blocking buttons
- Direct links to messages
- Rich text formatting with HTML

## Performance Optimizations

### Caching Strategy
1. **Content Cache**: `message_id -> (content, timestamp)`
2. **Processed Messages Set**: Track already handled messages
3. **Mainlist Cache**: 5-minute cache for forum list
4. **Database Integration**: Persistent caching across restarts

### Traffic Reduction Techniques
- **Conditional requests** based on cache status
- **Batch processing** of multiple messages
- **Smart pagination** with adaptive page sizes
- **Content deduplication** using real message IDs

## Deployment Process

### Git Integration
```bash
# Deploy to Azure
git push azure master

# Deploy to GitLab (backup)
git push origin master
```

### Build Process
- Oryx automatically detects Python 3.11
- Installs dependencies from requirements.txt
- Creates virtual environment
- Configures Gunicorn WSGI server

### Health Monitoring
- HTTP endpoints for status checking
- Application logs via Azure portal
- Automatic restart on deployment

## Error Handling & Resilience

### Network Resilience
- Request timeouts and retries
- Graceful degradation on RSDN unavailability
- Connection pooling for efficiency

### Data Consistency
- SQLite ACID transactions
- Cache invalidation strategies
- Duplicate message prevention

### Monitoring & Logging
- Structured logging throughout application
- Performance metrics collection
- Error tracking and debugging

## Future Enhancement Ideas

### Potential Improvements
1. **Advanced filtering** by keywords, authors, or topics
2. **Message threading** visualization
3. **Push notification** alternatives
4. **Analytics dashboard** for forum activity
5. **RSS feed** generation
6. **Mobile app** integration
7. **Machine learning** for content classification
8. **User statistics** and usage analytics

### Scalability Considerations
- Database migration to PostgreSQL for high-volume multi-chat usage
- Redis for distributed caching
- Load balancing for high traffic
- Microservices architecture separation
- Chat registration rate limiting

## Technical Decisions Rationale

### Why SQLite?
- Simple deployment on free tier
- ACID transactions
- No additional infrastructure cost
- Sufficient for moderate multi-chat usage
- Easy migration to PostgreSQL when needed

### Why Azure F1?
- Free tier availability
- Git deployment integration
- Python runtime support
- European data center location

### Why Telegram Bot API?
- Rich formatting support
- Inline keyboard interactions
- Reliable message delivery
- Easy setup and maintenance

### Why RSDN Mainlist API?
- Structured HTML table format
- Recent message indicators
- Direct message linking
- Minimal parsing complexity

## Development Workflow

### Local Development
```bash
# Environment setup
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Edit .env with your tokens

# Testing
python main.py
```

### Debugging Approach
1. **Isolated component testing** with temporary test files
2. **HTML structure analysis** for parsing fixes  
3. **Minimal change principle** for production stability
4. **Real-time monitoring** of Azure logs

This architecture provides a robust, scalable foundation for forum monitoring with efficient resource usage and excellent user experience.