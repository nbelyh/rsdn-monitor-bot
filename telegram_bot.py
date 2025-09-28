import logging
from typing import List, Optional, Set
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode
import html

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Handles Telegram bot notifications"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token)
    
    async def send_new_messages(self, messages: List['ForumMessage'], monitored_forums: Optional[Set[str]] = None):
        """Send notifications for new forum messages"""
        if not messages:
            return
        
        # Filter messages by monitored forums if specified
        if monitored_forums:
            messages = [msg for msg in messages if msg.forum in monitored_forums]
        
        if not messages:
            return
        
        try:
            # Group messages by forum for better organization
            messages_by_forum = {}
            for message in messages:
                if message.forum not in messages_by_forum:
                    messages_by_forum[message.forum] = []
                messages_by_forum[message.forum].append(message)
            
            # Send notifications for each forum
            for forum, forum_messages in messages_by_forum.items():
                if len(forum_messages) == 1:
                    await self._send_single_message_notification(forum_messages[0])
                else:
                    await self._send_multiple_messages_notification(forum, forum_messages)
                    
        except Exception as e:
            logger.error(f"Error sending Telegram notifications: {e}")
    
    async def _send_single_message_notification(self, message: 'ForumMessage'):
        """Send notification for a single message"""
        try:
            # Format the message
            text = self._format_message(message)
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )
            
        except Exception as e:
            logger.error(f"Error sending single message notification: {e}")
    
    async def _send_multiple_messages_notification(self, forum: str, messages: List['ForumMessage']):
        """Send notification for multiple messages from the same forum"""
        try:
            header = f"🔥 <b>{len(messages)} новых в {html.escape(forum)}</b>\n"
            
            message_lines = []
            for message in messages[:8]:  # Limit to 8 messages to keep it clean
                line = f"• <a href=\"{html.escape(message.url)}\">{html.escape(message.title)}</a>"
                line += f"\n  👤 {html.escape(message.author)}"
                if message.replies_count > 0:
                    line += f" • 💬 {message.replies_count}"
                    if message.last_reply_author:
                        line += f" (последний: {html.escape(message.last_reply_author)})"
                message_lines.append(line)
            
            text = header + "\n" + "\n\n".join(message_lines)
            
            if len(messages) > 8:
                text += f"\n\n... и ещё {len(messages) - 8}"
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            
        except Exception as e:
            logger.error(f"Error sending multiple messages notification: {e}")
    
    def _format_message(self, message: 'ForumMessage') -> str:
        """Format a single message for Telegram - clean and concise"""
        # Escape HTML characters
        title = html.escape(message.title)
        author = html.escape(message.author)
        forum = html.escape(message.forum)
        url = html.escape(message.url)
        
        # Build a clean, concise message
        text = f"� <b><a href=\"{url}\">{title}</a></b>\n"
        text += f"� {forum} • 👤 {author}"
        
        # Add reply info if there are replies
        if message.replies_count > 0:
            text += f" • 💬 {message.replies_count}"
            if message.last_reply_author:
                last_author = html.escape(message.last_reply_author)
                text += f" (последний: {last_author})"
        
        return text
    
    async def send_status_message(self, text: str):
        """Send a status message to the chat"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Error sending status message: {e}")
    
    async def test_connection(self) -> bool:
        """Test the Telegram bot connection"""
        try:
            await self.bot.get_me()
            logger.info("Telegram bot connection successful")
            return True
        except Exception as e:
            logger.error(f"Telegram bot connection failed: {e}")
            return False

class TelegramBotHandler:
    """Handles Telegram bot commands and interactions"""
    
    def __init__(self, bot_token: str, chat_id: str, database_manager: 'DatabaseManager'):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.db = database_manager
        self.application = None
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_text = """
🤖 <b>RSDN Forum Bot</b>

Этот бот отслеживает новые сообщения на форуме RSDN.org и присылает уведомления.

<b>Доступные команды:</b>
/start - Показать это сообщение
/status - Показать статус бота
/stats - Показать статистику сообщений

Бот автоматически сканирует форум каждую минуту.
        """
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.HTML
        )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            stats = self.db.get_stats()
            status_text = f"""
📊 <b>Статус RSDN Bot</b>

✅ Бот активен и работает
📝 Всего отслежено сообщений: {stats['total_messages']}

<b>Топ-форумы:</b>
"""
            for forum, count in stats['forum_stats'][:5]:
                status_text += f"• {forum}: {count} сообщений\n"
            
            await update.message.reply_text(
                status_text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await update.message.reply_text("❌ Ошибка при получении статуса")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        try:
            stats = self.db.get_stats()
            stats_text = f"""
📈 <b>Детальная статистика</b>

📝 <b>Всего сообщений:</b> {stats['total_messages']}

<b>Статистика по форумам:</b>
"""
            for forum, count in stats['forum_stats']:
                stats_text += f"• {forum}: {count}\n"
            
            await update.message.reply_text(
                stats_text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text("❌ Ошибка при получении статистики")
    
    def setup_handlers(self):
        """Setup command handlers"""
        if not self.application:
            self.application = Application.builder().token(self.bot_token).build()
        
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
    
    async def start_bot(self):
        """Start the Telegram bot"""
        try:
            self.setup_handlers()
            await self.application.initialize()
            await self.application.start()
            logger.info("Telegram bot started successfully")
        except Exception as e:
            logger.error(f"Error starting Telegram bot: {e}")
    
    async def stop_bot(self):
        """Stop the Telegram bot"""
        try:
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
            logger.info("Telegram bot stopped")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {e}")