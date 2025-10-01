import logging
from typing import List, Optional, Set
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError
import html

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Handles Telegram bot notifications"""
    
    def __init__(self, bot_token: str, db_manager: 'DatabaseManager' = None):
        self.bot_token = bot_token
        self.bot = Bot(token=bot_token)
        self.db = db_manager  # Add database manager for user filtering
    
    async def send_new_messages(self, messages: List['ForumMessage'], monitored_forums: Optional[Set[str]] = None):
        """Send notifications for new forum messages to all registered chats"""
        if not messages or not self.db:
            return
        
        # Filter messages by monitored forums if specified
        if monitored_forums:
            messages = [msg for msg in messages if msg.forum in monitored_forums]
        
        if not messages:
            return
        
        # Get all registered chats
        registered_chats = self.db.get_all_registered_chats()
        if not registered_chats:
            logger.info("No registered chats found for notifications")
            return
        
        # Send to each registered chat with their personal filters
        for chat_id in registered_chats:
            await self._send_messages_to_chat(chat_id, messages)
    
    async def _send_messages_to_chat(self, chat_id: str, messages: List['ForumMessage']):
        """Send messages to a specific chat with their personal filters"""
        try:
            # Get chat's blocked forums and filter them out
            chat_blocked_forums = self.db.get_chat_blocked_forums(chat_id)
            if chat_blocked_forums:
                filtered_messages = [msg for msg in messages if msg.forum not in chat_blocked_forums]
            else:
                filtered_messages = messages
            
            if not filtered_messages:
                return
            
            # Group messages by forum for better organization
            messages_by_forum = {}
            for message in filtered_messages:
                if message.forum not in messages_by_forum:
                    messages_by_forum[message.forum] = []
                messages_by_forum[message.forum].append(message)
            
            # Send notifications for each forum
            for forum, forum_messages in messages_by_forum.items():
                await self._send_forum_messages_notification(chat_id, forum, forum_messages)
                    
        except Exception as e:
            logger.error(f"Error sending Telegram notifications to chat {chat_id}: {e}")
    
    async def _send_forum_messages_notification(self, chat_id: str, forum: str, messages: List['ForumMessage']):
        """Send notification for messages from a forum (unified format with timestamps and filter button)"""
        try:
            # Header with forum name and count
            if len(messages) == 1:
                header = f"📝 <b>{html.escape(forum)}</b>\n"
            else:
                header = f"🔥 <b>{len(messages)} новых в {html.escape(forum)}</b>\n"
            
            message_lines = []
            for message in messages[:8]:  # Limit to 8 messages to keep it clean
                # Format: Author inline before title (compact and clean)
                # • 👤 Author: Title (both bold)
                #   URL
                #   "Preview"
                line = f"• 👤 <b>{html.escape(message.author)}: {html.escape(message.title)}</b>"
                
                # Add reply count if present
                if message.replies_count > 0:
                    line += f" • 💬 {message.replies_count}"
                
                # URL on its own line (plain text to avoid security prompts)
                line += f"\n  {message.url}"
                
                # Add last message text preview if available
                if message.last_message_text:
                    line += f"\n  <i>\"{html.escape(message.last_message_text)}\"</i>"
                
                message_lines.append(line)
            
            text = header + "\n" + "\n\n".join(message_lines)
            
            if len(messages) > 8:
                text += f"\n\n... и ещё {len(messages) - 8}"
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            
            # Reset failed delivery count on successful send
            if self.db:
                self.db.reset_failed_deliveries(chat_id)
            
        except Forbidden as e:
            # Bot was blocked by the user
            logger.warning(f"Bot blocked by user in chat {chat_id}: {e}")
            if self.db:
                failed_count = self.db.increment_failed_deliveries(chat_id)
                if failed_count >= 5:
                    logger.info(f"Unregistering chat {chat_id} after {failed_count} failed delivery attempts")
                    self.db.unregister_chat(chat_id)
        except TelegramError as e:
            # Other Telegram-specific errors (network issues, etc.)
            logger.error(f"Telegram error sending notification to chat {chat_id}: {e}")
        except Exception as e:
            logger.error(f"Error sending forum messages notification to chat {chat_id}: {e}")
    
    async def send_status_message(self, text: str, chat_id: str = None):
        """Send a status message to a specific chat or all registered chats"""
        try:
            if chat_id:
                # Send to specific chat
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML
                )
            else:
                # Send to all registered chats
                if self.db:
                    registered_chats = self.db.get_all_registered_chats()
                    for cid in registered_chats:
                        try:
                            await self.bot.send_message(
                                chat_id=cid,
                                text=text,
                                parse_mode=ParseMode.HTML
                            )
                        except Forbidden as e:
                            logger.warning(f"Bot blocked by user in chat {cid}: {e}")
                            failed_count = self.db.increment_failed_deliveries(cid)
                            if failed_count >= 5:
                                logger.info(f"Unregistering chat {cid} after {failed_count} failed delivery attempts")
                                self.db.unregister_chat(cid)
                        except Exception as e:
                            logger.error(f"Error sending status message to chat {cid}: {e}")
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
    
    def __init__(self, bot_token: str, database_manager: 'DatabaseManager', scan_interval_minutes: int = 1):
        self.bot_token = bot_token
        self.db = database_manager
        self.scan_interval_minutes = scan_interval_minutes
        self.application = None
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - register chat and show welcome"""
        chat_id = str(update.effective_chat.id)
        chat_title = getattr(update.effective_chat, 'title', None) or getattr(update.effective_user, 'first_name', 'Unknown')
        
        # Register the chat for notifications
        self.db.register_chat(chat_id, chat_title)
        
        # Reset failed delivery count when user re-activates the bot
        self.db.reset_failed_deliveries(chat_id)
        
        # Format interval display in Russian
        if self.scan_interval_minutes == 1:
            interval_text = "каждую минуту"
        elif 2 <= self.scan_interval_minutes <= 4:
            interval_text = f"каждые {self.scan_interval_minutes} минуты"
        else:
            interval_text = f"каждые {self.scan_interval_minutes} минут"
        
        welcome_text = f"""
🤖 <b>RSDN Forum Bot</b>

✅ Этот чат зарегистрирован для получения уведомлений о новых сообщениях на форуме RSDN.org!

<b>Доступные команды:</b>
/start - Показать это сообщение  
/stop - Отписаться от уведомлений
/status - Показать статус бота
/stats - Показать статистику сообщений
/filters - Управление фильтрами форумов

<b>Как фильтровать форумы:</b>
• Используйте команду /filters для интерактивного управления
• Все функции доступны в одном меню: блокировка, разблокировка, сброс фильтров

Бот автоматически сканирует форум {interval_text}.
        """
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.HTML
        )
    
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command - unregister chat"""
        chat_id = str(update.effective_chat.id)
        
        # Check if chat is registered
        if not self.db.is_chat_registered(chat_id):
            await update.message.reply_text(
                "❌ Этот чат не зарегистрирован для получения уведомлений.\n"
                "Используйте /start для регистрации."
            )
            return
        
        # Unregister the chat
        self.db.unregister_chat(chat_id)
        
        goodbye_text = """
👋 <b>До свидания!</b>

Этот чат отписан от уведомлений RSDN Forum Monitor.

Чтобы снова получать уведомления, используйте /start
        """
        
        await update.message.reply_text(
            goodbye_text,
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
            registered_chats_count = self.db.get_registered_chats_count()
            
            stats_text = f"""
📈 <b>Детальная статистика</b>

👥 <b>Зарегистрированных чатов:</b> {registered_chats_count}
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
        """Handle /filters command - show interactive forum filter menu"""
        try:
            chat_id = str(update.effective_chat.id)
            
            # Get all available forums and currently blocked forums
            all_forums = self.db.get_all_forums()
            blocked_forums = self.db.get_chat_blocked_forums(chat_id)
            
            if not all_forums:
                await update.message.reply_text(
                    "📋 <b>Фильтры форумов</b>\n\n"
                    "❌ Пока нет данных о форумах.\n"
                    "Дождитесь первого сканирования форума.",
                    parse_mode=ParseMode.HTML
                )
                return
            
            # Create header text
            header_text = f"📋 <b>Фильтры форумов</b> ({len(blocked_forums)} заблокировано из {len(all_forums)})\n\n"
            if blocked_forums:
                header_text += "Нажмите на форум чтобы изменить его статус:\n"
            else:
                header_text += "Выберите форумы для блокировки:\n"
            
            # Create inline keyboard with forums (show max 10 per page)
            keyboard = []
            for forum in sorted(all_forums):
                if forum in blocked_forums:
                    # Show as blocked with ✅ to unblock
                    button_text = f"🚫 {forum}"
                    callback_data = f"unblock_forum:{forum}"
                else:
                    # Show as allowed with ❌ to block
                    button_text = f"✅ {forum}"
                    callback_data = f"block_forum:{forum}"
                
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            if blocked_forums:
                keyboard.append([InlineKeyboardButton("🗑️ Сбросить все фильтры", callback_data="reset_all_filters")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                header_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error in filters command: {e}")
            await update.message.reply_text("❌ Ошибка при получении фильтров")
    

    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()
        
        try:
            chat_id = str(query.from_user.id)
            callback_data = query.data
            
            if callback_data.startswith('block_forum:'):
                forum = callback_data.replace('block_forum:', '')
                self.db.block_forum_for_chat(chat_id, forum)
                await query.answer(f"🚫 Форум {forum} заблокирован", show_alert=True)
                
                # Refresh the filters menu
                await self._refresh_filters_menu(query)
                
            elif callback_data.startswith('unblock_forum:'):
                forum = callback_data.replace('unblock_forum:', '')
                self.db.unblock_forum_for_chat(chat_id, forum)
                await query.answer(f"✅ Форум {forum} разблокирован", show_alert=True)
                
                # Refresh the filters menu
                await self._refresh_filters_menu(query)
                
            elif callback_data == 'reset_all_filters':
                deleted_count = self.db.reset_chat_forum_filters(chat_id)
                await query.answer(f"🗑️ Сброшено {deleted_count} фильтров", show_alert=True)
                
                # Refresh the filters menu
                await self._refresh_filters_menu(query)
                

                
        except Exception as e:
            logger.error(f"Error handling button callback: {e}")
            await query.answer("❌ Ошибка при обработке команды", show_alert=True)
    
    async def _refresh_filters_menu(self, query):
        """Refresh the filters menu after a change"""
        try:
            chat_id = str(query.from_user.id)
            
            # Get updated forum lists
            all_forums = self.db.get_all_forums()
            blocked_forums = self.db.get_chat_blocked_forums(chat_id)
            
            # Create updated header text
            header_text = f"📋 <b>Фильтры форумов</b> ({len(blocked_forums)} заблокировано из {len(all_forums)})\n\n"
            if blocked_forums:
                header_text += "Нажмите на форум чтобы изменить его статус:\n"
            else:
                header_text += "Выберите форумы для блокировки:\n"
            
            # Create updated keyboard
            keyboard = []
            for forum in sorted(all_forums):
                if forum in blocked_forums:
                    button_text = f"🚫 {forum}"
                    callback_data = f"unblock_forum:{forum}"
                else:
                    button_text = f"✅ {forum}"
                    callback_data = f"block_forum:{forum}"
                
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            if blocked_forums:
                keyboard.append([InlineKeyboardButton("🗑️ Сбросить все фильтры", callback_data="reset_all_filters")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=header_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error refreshing filters menu: {e}")
    
    def setup_handlers(self):
        """Setup command handlers"""
        if not self.application:
            self.application = Application.builder().token(self.bot_token).build()
        
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("stop", self.stop_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("filters", self.filters_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start_bot(self):
        """Start the Telegram bot with polling"""
        try:
            self.setup_handlers()
            await self.application.initialize()
            await self.application.start()
            
            # Register bot commands so they appear in Telegram UI
            await self._register_bot_commands()
            
            # Start polling for updates
            await self.application.updater.start_polling()
            logger.info("Telegram bot started successfully with polling")
        except Exception as e:
            logger.error(f"Error starting Telegram bot: {e}")
    
    async def _register_bot_commands(self):
        """Register bot commands with Telegram so they appear in the UI"""
        try:
            from telegram import BotCommand
            
            commands = [
                BotCommand("start", "🚀 Подписаться на уведомления"),
                BotCommand("stop", "🛑 Отписаться от уведомлений"),
                BotCommand("status", "📊 Показать статус бота"),
                BotCommand("stats", "📈 Статистика сообщений"),
                BotCommand("filters", "� Управление фильтрами форумов")
            ]
            
            await self.application.bot.set_my_commands(commands)
            logger.info("Bot commands registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to register bot commands: {e}")
    
    
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