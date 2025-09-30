# RSDN Bot - AI Coding Agent Instructions

## Project Documentation
This project has comprehensive documentation in several .md files:
- **README.md** - Main project overview, setup instructions, and basic usage
- **ARCHITECTURE.md** - Detailed system architecture and component relationships
- **TELEGRAM_SETUP.md** - Telegram bot configuration and API setup guide
- **DATABASE_SCHEMA.md** - SQLite database structure and table definitions
- **AZURE_CONFIG.md** - Azure App Service deployment configuration and settings
- **MIGRATIONS.md** - Database migration system and how to add new migrations

Reference these files for detailed context on specific aspects of the system.

## Architecture Overview
This is a **multi-user Telegram bot** that monitors RSDN.org forum for new messages and sends real-time notifications. Key architectural principle: **any chat can register via `/start` command** - no hardcoded chat IDs.

**Core Data Flow**: `RSDN Forum → scraper.py → database.py → telegram_bot.py → All Registered Chats`

### Critical Components
- **main.py** - Orchestrates with AsyncIOScheduler, loads env config, runs migrations on startup
- **scraper.py** - Parses RSDN mainlist HTML with traffic optimization (98% bandwidth reduction)
- **telegram_bot.py** - Handles multi-chat registration and per-chat forum filtering 
- **database.py** - SQLite with two main tables: `seen_messages` and `chat_preferences`
- **migrations.py** - Database schema migration system with version tracking
- **app.py** - Flask wrapper for Azure App Service deployment

## Key Implementation Patterns

### Multi-Chat Architecture
```python
# NO hardcoded chat IDs - users register dynamically
self.db.register_chat(chat_id, chat_title)  # via /start command
registered_chats = self.db.get_registered_chats()  # send to all
```

### Message ID Strategy (CRITICAL FIX)
```python
# Extract from SUBJECT link (not time link - time cells have no <a> tags)
subject_link = subject_cell.find('a')  # cells[2] 
latest_message_id = re.search(r'/forum/[^/]+/(\d+)', href).group(1)
```

### Recent Message Detection
```python
def _is_recent_message(self, time_text: str) -> bool:
    return 'мин' in time_text.lower().strip()  # Only process "23 мин" not "1 час"
```

### Zero-Reply vs Multi-Reply Logic
```python
# Different handling for new topics (0 replies) vs active threads (1+ replies)
author = last_reply_author if (replies_count > 0 and last_reply_author) else author
# Content fetching works for both, but presentation differs
```

## Configuration Patterns

### Environment Loading
```python
# CHECK_INTERVAL_MINUTES (not seconds) - converted internally
check_interval_minutes = int(os.getenv('CHECK_INTERVAL_MINUTES', '1'))
self.scan_interval = check_interval_minutes * 60  # Convert for scheduler
```

### Database Schema 
- `seen_messages`: Uses **real RSDN message IDs** (not hashes) as PRIMARY KEY
- `chat_preferences`: Key-value store per chat (`chat_id`, `preference_key`, `preference_value`)
- Multi-chat registration: `(chat_id, "registered", "true")`
- Forum filtering: `(chat_id, "blocked_forum", "forum_name")`

## Deployment & Development

### Local Development
```bash
cp .env.example .env  # Configure TELEGRAM_BOT_TOKEN
python main.py        # Standalone mode
```

### Azure Deployment  
```bash
git push azure master  # Triggers automatic deployment
# Uses app.py Flask wrapper, runs via Gunicorn
```

### Testing Strategy
```python
# Create isolated test files for parsing logic
# Use real RSDN URLs: https://rsdn.org/forum/mainlist/all?start=0&pageSize=10
# Test both zero-reply and multi-reply message scenarios
```

## Critical Implementation Details

### Traffic Optimization
- **Content caching**: `_content_cache: Dict[str, tuple]` with 5-minute timeout
- **Processed message tracking**: `_processed_messages: Set[str]` to avoid re-fetching
- **Adaptive page sizing**: Reduces page size when cache hit ratio > 80%

### Telegram Bot Features
- **Inline keyboards**: "🚫 Don't show messages from [forum]" buttons
- **Per-chat filtering**: Independent forum preferences per registered chat
- **Dynamic commands**: `/start`, `/stop`, `/status`, `/stats`, `/filters`
- **Russian localization**: Time intervals and messages in Russian

### HTML Parsing Specifics
```python
# RSDN mainlist structure (8 columns):
# 0: Time, 1: Forum, 2: Subject+Link, 3: Author, 4: Reply count, 5: Last reply author
cells = row.find_all('td')
subject_link = cells[2].find('a')  # Critical: get message ID from here
```

## Common Development Tasks

### Adding New Commands
1. Add handler in `TelegramBotHandler.__init__()`
2. Implement `async def command_name(update, context)`
3. Update `/start` welcome text with new command

### Modifying Message Format
- Edit `_send_forum_messages_notification()` in `telegram_bot.py`
- Use `html.escape()` for all user content
- Format: `👤 author • 🕐 time • 💬 replies`

### Database Migrations
- Add new migration in `migrations.py` using `MigrationManager.get_migrations()`
- Migrations run automatically on startup (both local and Azure)
- Use version numbers sequentially (1, 2, 3...)
- Always backup data before destructive operations
- Test locally with `python migrations.py` before deploying
- See **MIGRATIONS.md** for detailed guide on adding migrations

### Forum Filtering Logic
- User blocks via inline buttons → stored as `chat_preferences`
- Filter in `send_new_messages()` before sending notifications
- Each chat maintains independent filter lists