import logging
from typing import List, Optional, Set
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
import html

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Handles Telegram bot notifications"""
    
    def __init__(self, bot_token: str, chat_id: str, db_manager: 'DatabaseManager' = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token)
        self.db = db_manager  # Add database manager for user filtering
    
    async def send_new_messages(self, messages: List['ForumMessage'], monitored_forums: Optional[Set[str]] = None):
        """Send notifications for new forum messages with user filtering"""
        if not messages:
            return
        
        # Filter messages by monitored forums if specified
        if monitored_forums:
            messages = [msg for msg in messages if msg.forum in monitored_forums]
        
        # Get user's blocked forums and filter them out
        if self.db:
            user_blocked_forums = self.db.get_user_blocked_forums(self.chat_id)
            if user_blocked_forums:
                messages = [msg for msg in messages if msg.forum not in user_blocked_forums]
        
        if not messages:
            return
        
        try:
            # Group messages by forum for better organization
            messages_by_forum = {}
            for message in messages:
                if message.forum not in messages_by_forum:
                    messages_by_forum[message.forum] = []
                messages_by_forum[message.forum].append(message)
            
            # Send notifications for each forum (always use grouped format)
            for forum, forum_messages in messages_by_forum.items():
                await self._send_forum_messages_notification(forum, forum_messages)
                    
        except Exception as e:
            logger.error(f"Error sending Telegram notifications: {e}")
    
    async def _send_forum_messages_notification(self, forum: str, messages: List['ForumMessage']):
        """Send notification for messages from a forum (unified format with timestamps and filter button)"""
        try:
            # Header with forum name and count
            if len(messages) == 1:
                header = f"📝 <b>{html.escape(forum)}</b>\n"
            else:
                header = f"🔥 <b>{len(messages)} новых в {html.escape(forum)}</b>\n"
            
            message_lines = []
            for message in messages[:8]:  # Limit to 8 messages to keep it clean
                line = f"• <a href=\"{html.escape(message.url)}\">{html.escape(message.title)}</a>"
                
                # Show author flow: original → latest reply author
                if message.last_reply_author and message.replies_count > 0:
                    # Get original author from the title parsing or use a different approach
                    # For now, we'll show the latest reply author as the main author
                    line += f"\n  👤 {html.escape(message.author)} • 🕐 {html.escape(message.time_posted)}"
                    line += f" • 💬 {message.replies_count} ответов"
                else:
                    line += f"\n  � {html.escape(message.author)} • 🕐 {html.escape(message.time_posted)}"
                    if message.replies_count > 0:
                        line += f" • 💬 {message.replies_count}"
                
                # Add last message text preview if available
                if message.last_message_text:
                    line += f"\n  <i>\"{html.escape(message.last_message_text)}\"</i>"
                
                message_lines.append(line)
            
            text = header + "\n" + "\n\n".join(message_lines)
            
            if len(messages) > 8:
                text += f"\n\n... и ещё {len(messages) - 8}"
            
            # Always add inline button to filter this forum
            keyboard = [
                [InlineKeyboardButton(
                    f"🚫 Не показывать сообщения из {forum}", 
                    callback_data=f"block_forum:{forum}"
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error sending forum messages notification: {e}")
    
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
    
    def __init__(self, bot_token: str, chat_id: str, database_manager: 'DatabaseManager', scan_interval_minutes: int = 1):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.db = database_manager
        self.scan_interval_minutes = scan_interval_minutes
        self.application = None
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        # Format interval display in Russian
        if self.scan_interval_minutes == 1:
            interval_text = "каждую минуту"
        elif 2 <= self.scan_interval_minutes <= 4:
            interval_text = f"каждые {self.scan_interval_minutes} минуты"
        else:
            interval_text = f"каждые {self.scan_interval_minutes} минут"
        
        welcome_text = f"""
🤖 <b>RSDN Forum Bot</b>

Этот бот отслеживает новые сообщения на форуме RSDN.org и присылает уведомления.

<b>Доступные команды:</b>
/start - Показать это сообщение
/status - Показать статус бота
/stats - Показать статистику сообщений
/filters - Показать текущие фильтры форумов
/reset_filters - Сбросить все фильтры форумов

<b>Как фильтровать форумы:</b>
• Используйте кнопку "🚫 Не показывать..." под сообщениями
• Просмотрите активные фильтры: /filters  
• Сбросьте все фильтры: /reset_filters

Бот автоматически сканирует форум {interval_text}.
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
    
    async def filters_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /filters command - show current forum filters"""
        try:
            user_id = str(update.effective_user.id)
            blocked_forums = self.db.get_user_blocked_forums(user_id)
            
            if not blocked_forums:
                await update.message.reply_text(
                    "📋 <b>Фильтры форумов</b>\n\n"
                    "✅ Все форумы разрешены\n"
                    "💡 Используйте кнопку '🚫 Не показывать...' под сообщениями для блокировки форумов",
                    parse_mode=ParseMode.HTML
                )
            else:
                filters_text = "📋 <b>Заблокированные форумы:</b>\n\n"
                for forum in sorted(blocked_forums):
                    filters_text += f"🚫 {forum}\n"
                
                filters_text += "\n💡 Используйте /reset_filters для сброса всех фильтров"
                
                await update.message.reply_text(
                    filters_text,
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Error in filters command: {e}")
            await update.message.reply_text("❌ Ошибка при получении фильтров")
    
    async def reset_filters_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reset_filters command - reset all forum filters"""
        try:
            user_id = str(update.effective_user.id)
            deleted_count = self.db.reset_user_forum_filters(user_id)
            
            if deleted_count > 0:
                await update.message.reply_text(
                    f"✅ <b>Фильтры сброшены</b>\n\n"
                    f"Разблокировано форумов: {deleted_count}\n"
                    f"Теперь вы получаете уведомления из всех форумов.",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    "📋 У вас нет активных фильтров форумов",
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Error in reset filters command: {e}")
            await update.message.reply_text("❌ Ошибка при сбросе фильтров")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()
        
        try:
            user_id = str(query.from_user.id)
            callback_data = query.data
            
            if callback_data.startswith('block_forum:'):
                forum = callback_data.replace('block_forum:', '')
                self.db.block_forum_for_user(user_id, forum)
                
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            f"✅ Форум {forum} заблокирован", 
                            callback_data="blocked"
                        )],
                        [InlineKeyboardButton(
                            "🔄 Разблокировать", 
                            callback_data=f"unblock_forum:{forum}"
                        )]
                    ])
                )
                
            elif callback_data.startswith('unblock_forum:'):
                forum = callback_data.replace('unblock_forum:', '')
                self.db.unblock_forum_for_user(user_id, forum)
                
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            f"✅ Форум {forum} разблокирован", 
                            callback_data="unblocked"
                        )]
                    ])
                )
                
        except Exception as e:
            logger.error(f"Error handling button callback: {e}")
            await query.message.reply_text("❌ Ошибка при обработке команды")
    
    def setup_handlers(self):
        """Setup command handlers"""
        if not self.application:
            self.application = Application.builder().token(self.bot_token).build()
        
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("filters", self.filters_command))
        self.application.add_handler(CommandHandler("reset_filters", self.reset_filters_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start_bot(self):
        """Start the Telegram bot with polling"""
        try:
            self.setup_handlers()
            await self.application.initialize()
            await self.application.start()
            
            # Start polling for updates
            await self.application.updater.start_polling()
            logger.info("Telegram bot started successfully with polling")
        except Exception as e:
            logger.error(f"Error starting Telegram bot: {e}")
    
    async def stop_bot(self):
        """Stop the Telegram bot"""
        try:
            if self.application and self.application.updater:
                await self.application.updater.stop()
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
            logger.info("Telegram bot stopped")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {e}")