import os
import telebot
from telebot import types
import logging
import traceback
from colorama import Fore

from Utils import telegram_tools


# Логгер
logger = logging.getLogger("TGBot")

# Основная клавиатура
mainKeyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
mainKeyboard.row("📟 Команды 📟")
mainKeyboard.row("🤖 О боте 🤖")
mainKeyboard.row("📋 Логи 📋")

# Сообщение со списком команд.
commands_text = """/add_chat - добавляет чат в список чатов для уведомлений.
/remove_chat - удаляет чат и списка чатов для уведомлений.
/menu - открывает меню."""

# Сообщение с информацией о боте.
about_text = """WSB FunPay - это продвинутый бот для автоматизации рутинных действий.
Разработчик:
    TG: @woopertail
    VK: https://vk.com/woopertail
    GitHub: https://github.com/woopertail

Скачать бота:
https://github.com/woopertail/WSB_FunPay
"""


class TGBot:
    def __init__(self, main_config):
        self.main_config = main_config
        self.bot = telebot.TeleBot(main_config["Telegram"]["token"])

        self.authorized_users = telegram_tools.load_authorized_users()
        self.chat_ids = telegram_tools.load_chat_ids()

    def init(self):
        self.__init_commands()
        logger.info("Telegram бот инициализирован.")

    def __init_commands(self):
        bot_instance = self.bot

        @bot_instance.message_handler(func=lambda msg: msg.from_user.id not in self.authorized_users)
        def reg_admin(message: types.Message):
            try:
                if message.text == self.main_config["Telegram"]["secretKey"]:
                    if message.chat.type != "private":
                        return
                    if message.from_user.id not in self.authorized_users:
                        self.authorized_users.append(message.from_user.id)
                        telegram_tools.save_authorized_users(self.authorized_users)
                        text = f"""⭐️ Та-даааам! Теперь я тебе доверяю."""
                        self.bot.send_message(message.chat.id, text, reply_markup=mainKeyboard)

                elif message.from_user.id not in self.authorized_users:
                    if message.chat.type != "private":
                        return
                    text = f"""👋 Привет, {message.from_user.username}!
    🫤 Похоже, ты неавторизированный пользователь.
    🔑 Отправь мне секретный пароль который ты ввел в моих настройках, что бы начать работу 🙂"""
                    self.bot.send_message(message.chat.id, text)
                return
            except:
                logger.error("Произошла ошибка в работе Telegram бота.")
                logger.debug(traceback.format_exc())

        @bot_instance.message_handler()
        def process_command(message: types.Message):
            try:
                if message.text == "/add_chat":
                    if message.chat.id in self.chat_ids:
                        self.bot.send_message(message.chat.id,
                                              "❌ Данный чат уже находится в списке чатов для уведомлений.")
                    else:
                        self.chat_ids.append(message.chat.id)
                        telegram_tools.save_chat_ids(self.chat_ids)
                        self.bot.send_message(message.chat.id,
                                              "✔️ Теперь в этот чат будут приходить уведомления.")

                elif message.text == "/remove_chat":
                    if message.chat.id not in self.chat_ids:
                        self.bot.send_message(message.chat.id,
                                              "❌ Данного чата нет в списке чатов для уведомлений.")
                    else:
                        self.chat_ids.remove(message.chat.id)
                        telegram_tools.save_chat_ids(self.chat_ids)
                        self.bot.send_message(message.chat.id,
                                              "✔️ Теперь в этот чат не будут приходить уведомления.")

                elif message.text == "/menu":
                    self.bot.send_message(message.chat.id, "Меню", reply_markup=mainKeyboard)

                # Команды с кнопок
                elif message.text == "📟 Команды 📟":
                    self.bot.send_message(message.chat.id, commands_text)

                elif message.text == "🤖 О боте 🤖":
                    self.bot.send_message(message.chat.id, about_text)

                elif message.text == "📋 Логи 📋":
                    if not os.path.exists("logs/log.log"):
                        self.bot.send_message(message.chat.id, "❌ Лог файл не обнаружен.")
                    else:
                        with open("logs/log.log", "r", encoding="utf-8") as f:
                            self.bot.send_document(message.chat.id, f)
            except:
                logger.error("Произошла ошибка в работе Telegram бота.")
                logger.debug(traceback.format_exc())

    def send_notification(self, text: str):
        for chat_id in self.chat_ids:
            try:
                self.bot.send_message(chat_id, text)
            except:
                logger.error("Произошла ошибка при отправке уведомления в Telegram.")
                logger.debug(traceback.format_exc())

    def run(self):
        try:
            logger.info(f"Telegram бот @{self.bot.user.username} запущен.")
            self.bot.infinity_polling(logger_level=logging.DEBUG)
        except:
            logger.error("Произошла ошибка при получении обновлений Telegram (введен некорректный токен?).")
            logger.debug(traceback.format_exc())
