# RSDN Forum Telegram Bot

A Telegram bot that monitors the RSDN.org forum for new messages and sends notifications.

## Features

- 🔄 Periodic scanning of RSDN forum (configurable interval)
- 📱 Telegram notifications for new posts
- 🎯 Forum-specific filtering (monitor specific forums)
- 🙋 "Only my topics" mode: new topics + replies in topics you posted in (`/nick`, `/mine`)
- 📊 Built-in statistics and status commands
- 🗃️ SQLite database for tracking seen messages
- 🛡️ Duplicate detection to avoid spam
- 🧹 Automatic cleanup of old messages

## Quick Start Guide

### 🤖 **Step-by-Step Setup (5 minutes)**

1. **Create your Telegram bot:**
   - 📋 **[Click here for detailed bot setup instructions](TELEGRAM_SETUP.md)**
   - Quick version: Message [@BotFather](https://t.me/BotFather) → `/newbot` → save your bot token

2. **Get your Chat ID:**
   - Message [@userinfobot](https://t.me/userinfobot) in Telegram to get your Chat ID
   - Alternative methods in the [detailed setup guide](TELEGRAM_SETUP.md)

3. **Install and configure:**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Copy configuration template
   copy .env.example .env
   
   # Edit .env with your bot token and chat ID
   notepad .env
   ```

4. **Test and run:**
   ```bash
   # Test configuration
   python test_bot.py
   
   # Start the bot
   python main.py
   ```

That's it! Your bot will now monitor RSDN forum and send notifications to your Telegram.

---

## Setup

### 1. Prerequisites

- Python 3.8+
- Telegram Bot Token (see detailed instructions below)
- Your Telegram Chat ID (see detailed instructions below)

### 2. Create Telegram Bot

Before installing the bot, you need to create a Telegram bot and get your credentials:

#### **Step 1: Create a Telegram Bot**

1. **Open Telegram** and search for `@BotFather`
2. **Start a chat** with BotFather by clicking "Start" or sending `/start`
3. **Create a new bot** by sending the command:
   ```
   /newbot
   ```
4. **Choose a name** for your bot (this is the display name users will see):
   ```
   RSDN Forum Monitor
   ```
5. **Choose a username** for your bot (must end with 'bot'):
   ```
   RsdnMonitorBot
   ```
   *Note: The username must be unique. If taken, try variations like `rsdn_forum_bot`, `my_rsdn_bot`, etc.*

6. **Save your bot token** - BotFather will give you a token that looks like:
   ```
   8358189437:AAE-4JEZHKlFmWRWlDj1YNdPpogycokYPSM
   ```
   ⚠️ **Keep this token secret!** Anyone with this token can control your bot.

#### **Step 2: Get Your Chat ID**

You need to know where to send notifications. Here are several ways to get your chat ID:

**Method 1: Using @userinfobot (Recommended)**
1. Search for `@userinfobot` in Telegram
2. Start a chat and send any message
3. The bot will reply with your user information including your Chat ID

**Method 2: Using your bot**
1. Start a chat with your newly created bot (search for the username you chose)
2. Send any message to your bot (like "Hello")
3. Open this URL in your browser (replace `YOUR_BOT_TOKEN` with your actual token):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
4. Look for `"chat":{"id":123456789}` in the response - that number is your Chat ID

**Method 3: Using a group chat**
If you want notifications in a group:
1. Add your bot to the group
2. Make the bot an admin (optional but recommended)
3. Send a message in the group mentioning the bot: `@your_bot_username hello`
4. Use the getUpdates URL method above
5. Look for the group chat ID (will be negative, like `-123456789`)

#### **Step 3: Configure Bot Settings (Optional)**

You can customize your bot further:

1. **Set bot description** (what users see before starting chat):
   ```
   /setdescription
   ```
   Then choose your bot and enter:
   ```
   This bot monitors RSDN.org forum and sends notifications about new messages.
   ```

2. **Bot commands** are set automatically when the bot starts, but you can also set them manually:
   ```
   /setcommands
   ```
   Then choose your bot and enter:
   ```
   start - 🚀 Subscribe to notifications
   stop - 🛑 Unsubscribe from notifications  
   status - 📊 Show bot status
   stats - 📈 Message statistics
   filters - 🔍 Current forum filters
   reset_filters - 🗑️ Reset all filters
   ```

3. **Set bot photo** (optional):
   ```
   /setuserpic
   ```
   Then choose your bot and upload an image.

### 3. Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create configuration file:
   ```bash
   copy .env.example .env
   ```

4. Edit `.env` file with your settings:

   **Important: Replace these values with your actual credentials!**

   ```env
   # Replace with your actual bot token from BotFather
   TELEGRAM_BOT_TOKEN=8358189437:AAE-4JEZHKlFmWRWlDj1YNdPpogycokYPSM
   
   # How often to check for new messages (in minutes)
   CHECK_INTERVAL_MINUTES=1
   
   # Optional: Monitor only specific forums (comma-separated)
   # Leave empty to monitor all forums
   MONITORED_FORUMS=network,life,flame.comp
   ```

   **⚠️ Security Notes:**
   - Never share your bot token publicly
   - Never commit the `.env` file to version control
   - The `.env` file is already ignored in `.gitignore`

### 3. Using the Bot

The bot now supports multiple chats and users! Anyone can use it:

1. **Start the bot**: Send `/start` to register your chat for notifications
2. **Customize**: Use `/forums` to see available forums and `/block_forum` to filter
3. **Stop notifications**: Send `/stop` to unregister your chat

### 4. Running the Bot

```bash
python main.py
```

The bot will:
- Test connections to RSDN and Telegram
- Start monitoring the forum
- Send notifications for new messages
- Respond to Telegram commands

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | *Required* |
| `CHECK_INTERVAL_MINUTES` | How often to check for new messages (in minutes) | 1 |
| `RSDN_URL` | RSDN forum URL | https://rsdn.org/forum/ |
| `DATABASE_FILE` | SQLite database file path | rsdn_messages.db |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | INFO |
| `LOG_FILE` | Log file path | rsdn_bot.log |
| `MONITORED_FORUMS` | Comma-separated list of forums to monitor | *All forums* |

### Forum Filtering

To monitor specific forums only, set `MONITORED_FORUMS` in your `.env` file:

```env
# Monitor only these forums
MONITORED_FORUMS=network,life,flame.comp,abroad

# Monitor all forums (leave empty)
MONITORED_FORUMS=
```

Common RSDN forums:
- `network` - Сетевые технологии
- `life` - Жизнь программистов
- `flame.comp` - Computer flame
- `flame.politics.unfiltered` - Политика
- `abroad` - За рубежом
- `humour` - Юмор

## Telegram Commands

Once the bot is running, you can use these commands in Telegram:

- `/start` - 🚀 Register your chat for notifications and show welcome message
- `/stop` - 🛑 Unregister your chat from notifications  
- `/status` - 📊 Show bot status and basic statistics
- `/stats` - 📈 Show detailed forum message statistics
- `/filters` - 🔍 Show your current forum filters
- `/reset_filters` - 🗑️ Reset all your forum filters

**Interactive Features:**
- Use the "🚫 Don't show messages from [forum]" buttons under messages to filter forums
- All commands work independently per chat (personal chats, groups, channels)
- Each chat maintains its own forum filtering preferences

## Project Structure

```
rsdnbot/
├── main.py              # Main bot application
├── database.py          # Database management and models
├── scraper.py           # RSDN forum scraper
├── telegram_bot.py      # Telegram bot integration
├── requirements.txt     # Python dependencies
├── .env.example         # Configuration template
└── README.md           # This file
```

## How It Works

1. **Scraping**: The bot periodically scrapes the RSDN forum main page to get recent messages
2. **Detection**: New messages are identified by comparing against a local SQLite database
3. **Filtering**: Messages are filtered by monitored forums (if configured)
4. **Notification**: New messages are formatted and sent via Telegram
5. **Storage**: Message metadata is stored to prevent duplicate notifications

## Message Format

Telegram notifications include:
- Forum name
- Message title (with link)
- Author name
- Post time
- Reply count (if any)
- Last reply author (if any)

## Error Handling

The bot includes comprehensive error handling:
- Connection failures are logged and retried
- Parsing errors don't stop the bot
- Failed notifications are logged
- Status updates are sent for critical errors

## Maintenance

- The bot automatically cleans up messages older than 30 days
- Logs are written to both file and console
- Database is automatically created and managed

## Troubleshooting

### Bot doesn't start
- Check your `.env` file configuration
- Verify your Telegram bot token and chat ID
- Ensure RSDN.org is accessible from your network

### No notifications received
- Check if the bot is running without errors
- Verify your chat ID is correct
- Check if there are actually new messages in monitored forums
- Look at the log file for any errors

### Too many notifications
- Increase `CHECK_INTERVAL_MINUTES` to reduce frequency
- Use `MONITORED_FORUMS` to filter specific forums only
- Check if the database was reset (causing all messages to appear as new)

## License

This project is open source. Feel free to modify and distribute as needed.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues and questions:
1. Check the logs in `rsdn_bot.log`
2. Review this README
3. Create an issue with detailed error information