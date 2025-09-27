# Telegram Bot Setup Guide

This guide will walk you through creating a Telegram bot and getting the credentials needed for the RSDN Bot.

## 🤖 Creating Your Telegram Bot

### Step 1: Open BotFather

1. **Open Telegram** on your phone or computer
2. **Search for** `@BotFather` (this is Telegram's official bot for creating bots)
3. **Start a conversation** by clicking "Start" or sending `/start`

### Step 2: Create a New Bot

1. **Send the command**: `/newbot`
2. **BotFather will ask for a name** - this is the display name users will see:
   ```
   RSDN Forum Monitor
   ```
   (You can choose any name you like)

3. **BotFather will ask for a username** - this must be unique and end with 'bot':
   ```
   RsdnMonitorBot
   ```
   If this username is taken, try variations like:
   - `my_rsdn_bot`
   - `rsdn_forum_bot`
   - `rsdn_notifications_bot`
   - `your_name_rsdn_bot`

4. **Save your bot token** - BotFather will give you a token that looks like this:
   ```
   8358189437:AAE-4JEZHKlFmWRWlDj1YNdPpogycokYPSM
   ```
   
   ⚠️ **IMPORTANT**: Keep this token secret! Anyone with this token can control your bot.

## 💬 Getting Your Chat ID

You need to tell the bot where to send notifications. Here are three methods:

### Method 1: Using @userinfobot (Easiest)

1. **Search for** `@userinfobot` in Telegram
2. **Start a chat** and send any message like "hi"
3. **The bot will reply** with your user information including your **Chat ID**
4. **Copy the Chat ID** number (like `123456789`)

### Method 2: Using Your Own Bot

1. **Find your bot** in Telegram (search for the username you created)
2. **Start a chat** with your bot and send any message like "hello"
3. **Open this URL** in your web browser (replace `YOUR_BOT_TOKEN` with your actual token):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
4. **Look for** `"chat":{"id":123456789}` in the response
5. **That number** (123456789) is your Chat ID

### Method 3: For Group Chats

If you want notifications sent to a group instead of directly to you:

1. **Create a group** or use an existing one
2. **Add your bot** to the group
3. **Make the bot an admin** (recommended for reliability)
4. **Send a message** in the group mentioning your bot: `@your_bot_username hello`
5. **Use Method 2** above to get updates - look for the group chat ID
6. **Group chat IDs are negative** numbers (like `-123456789`)

## 🔧 Optional: Customize Your Bot

### Set Bot Description

This is what users see before starting a chat with your bot:

1. Send `/setdescription` to BotFather
2. Choose your bot
3. Enter:
   ```
   This bot monitors RSDN.org forum and sends notifications about new messages.
   ```

### Set Bot Commands

This creates a menu of available commands:

1. Send `/setcommands` to BotFather
2. Choose your bot
3. Enter:
   ```
   start - Show welcome message and help
   status - Show bot status and statistics
   stats - Show detailed forum statistics
   ```

### Set Bot Profile Picture

1. Send `/setuserpic` to BotFather
2. Choose your bot
3. Upload an image (optional)

## 📝 What You Need to Save

After completing the setup, you should have:

1. **Bot Token**: Something like `8358189437:AAE-4JEZHKlFmWRWlDj1YNdPpogycokYPSM`
2. **Chat ID**: A number like `123456789` (or negative for groups)

## ✅ Testing Your Setup

Before configuring the RSDN bot, test that everything works:

1. **Send a message** to your bot in Telegram
2. **Check that you can find your bot** by its username
3. **Make sure you have both** the bot token and chat ID

## 🔒 Security Best Practices

- **Never share** your bot token publicly
- **Don't commit** the bot token to code repositories
- **Store tokens** in environment variables or config files that are not shared
- **Regenerate the token** if you think it might be compromised (use `/revoke` with BotFather)

## 🆘 Troubleshooting

### "Username is already taken"
Try adding your name or numbers to make it unique: `john_rsdn_bot`, `rsdn_bot_2024`

### "Can't find my bot"
Make sure you're searching for the exact username (with underscores, without @)

### "Bot doesn't respond"
- Make sure you clicked "Start" in the chat
- Check that you're using the correct bot username
- Try creating a new bot if issues persist

### "Can't get Chat ID"
- Make sure you sent a message to your bot first
- Check the browser URL is correct (no spaces in the token)
- Try the @userinfobot method instead

---

## Next Steps

Once you have your bot token and chat ID:

1. **Go back to the main README.md**
2. **Follow the installation instructions**
3. **Put your credentials in the `.env` file**
4. **Run the bot!**

Need help? Check the main README.md for troubleshooting tips or create an issue with your error details.