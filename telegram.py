"""
В данном модуле написан Telegram бот.
"""


from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cardinal import Cardinal

import os
import telebot
from telebot import types
import logging
import traceback

from Utils import telegram_tools

from FunPayAPI.runner import MessageEvent


# Логгер
logger = logging.getLogger("TGBot")

# Основная клавиатура
mainKeyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
mainKeyboard.row("📟 Команды 📟")
mainKeyboard.row("🤖 О боте 🤖")
mainKeyboard.row("📋 Логи 📋")

# Сообщение с информацией о боте.
about_text = """WSB FunPay - это продвинутый бот для автоматизации рутинных действий.
Разработчик:
    TG: @woopertail
    VK: https://vk.com/woopertail
    GitHub: https://github.com/woopertail

Скачать бота:
https://github.com/woopertail/WSB_FunPay
"""


def create_cancel_reply_button():
    keyboard = telebot.types.InlineKeyboardMarkup()
    reply_button = telebot.types.InlineKeyboardButton(text="Отмена", callback_data=f"cancel_node_reply")
    keyboard.add(reply_button)
    return keyboard


def check_user_replying_to_node(reply_statuses, msg: types.Message):
    chat_id = msg.chat.id
    user_id = msg.from_user.id
    if chat_id in reply_statuses and user_id in reply_statuses[chat_id] and \
            reply_statuses[chat_id][user_id].startswith("reply_to_node_id:"):
        return True
    return False


class TGBot:
    def __init__(self, main_config):
        self.main_config = main_config
        self.bot = telebot.TeleBot(main_config["Telegram"]["token"])

        self.authorized_users = telegram_tools.load_authorized_users()
        self.chat_ids = telegram_tools.load_chat_ids()

        self.cardinal: Cardinal | None = None
        # {chat_id: {user_id: reply_type}
        self.user_reply_statuses: dict[int, dict[int, str]] = {}

        self.commands_help = {
            "FunPayCardinal": {
                "/add_chat": "добавляет чат в список чатов для уведомлений.",
                "/remove_chat": "удаляет чат и списка чатов для уведомлений.",
                "/menu": "открывает меню."
            }
        }

    def init(self):
        self.__init_commands()
        logger.info("$MAGENTATelegram бот инициализирован.")

    def __init_commands(self):
        """
        Регистрирует хэндлеры.
        """
        bot_instance = self.bot
        reply_statuses = self.user_reply_statuses
        authorized_users = self.authorized_users

        # Если сообщение пришло не от авторизированного пользователя.
        @bot_instance.message_handler(func=lambda msg: msg.from_user.id not in authorized_users)
        def reg_admin(message: types.Message):
            try:
                if message.text == self.main_config["Telegram"]["secretKey"]:
                    if message.chat.type != "private":
                        return
                    self.authorized_users.append(message.from_user.id)
                    telegram_tools.save_authorized_users(self.authorized_users)
                    text = f"""⭐️ Та-даааам! Теперь я тебе доверяю."""
                    self.bot.send_message(message.chat.id, text, reply_markup=mainKeyboard)

                else:
                    if message.chat.type != "private":
                        return
                    text = f"""👋 Привет, {message.from_user.username}!
🫤 Похоже, ты неавторизированный пользователь.
🔑 Отправь мне секретный пароль который ты ввел в моих настройках, что бы начать работу 🙂"""
                    self.bot.send_message(message.chat.id, text)
            except:
                logger.error("Произошла ошибка в работе Telegram бота.")
                logger.debug(traceback.format_exc())

        @bot_instance.callback_query_handler(func=lambda call: call.data.startswith("reply_to_node_id:"))
        def reply(call: types.CallbackQuery):
            try:
                user_id = call.from_user.id
                chat_id = call.message.chat.id
                self.bot.send_message(chat_id, "Введите ответ на сообщение.",
                                      reply_markup=create_cancel_reply_button())
                if chat_id not in self.user_reply_statuses:
                    self.user_reply_statuses[chat_id] = {}
                self.user_reply_statuses[chat_id][user_id] = \
                    f"reply_to_node_id:{call.data.split(':')[1]}"
                self.bot.answer_callback_query(call.id)
            except:
                logger.error("Произошла ошибка в работе Telegram бота.")
                logger.debug(traceback.format_exc())

        @bot_instance.callback_query_handler(func=lambda call: call.data.startswith("cancel_node_reply"))
        def cancel_reply(call: types.CallbackQuery):
            try:
                user_id = call.from_user.id
                chat_id = call.message.chat.id
                if chat_id in self.user_reply_statuses and user_id in self.user_reply_statuses[chat_id] and \
                        self.user_reply_statuses[chat_id][user_id].startswith("reply_to_node_id:"):
                    self.user_reply_statuses[chat_id].pop(user_id)
                    self.bot.send_message(chat_id, "Ок.")
                    self.bot.answer_callback_query(call.id)
                else:
                    self.bot.send_message(chat_id, "А ты и не отвечал на это сообщение так-то.")
                    self.bot.answer_callback_query(call.id)
            except:
                logger.error("Произошла ошибка в работе Telegram бота.")
                logger.debug(traceback.format_exc())

        @bot_instance.message_handler(func=lambda msg: check_user_replying_to_node(reply_statuses, msg))
        def send_reply_message(message: types.Message):
            try:
                chat_id = message.chat.id
                user_id = message.from_user.id
                if not self.cardinal:
                    self.bot.send_message(chat_id, "Ошибка. Кардинал не инициализирован. Верни меня на место!")
                    self.user_reply_statuses[chat_id].pop(user_id)
                    return
                node_id = int(self.user_reply_statuses[chat_id][user_id].split(":")[1])
                new_msg_obj = MessageEvent(node_id, message.text, None, None, None)
                try:
                    self.cardinal.send_message(new_msg_obj)
                    self.bot.send_message(chat_id, "Получилось.")
                except:
                    self.bot.send_message(chat_id, "Ошибка.")
                    logger.debug(traceback.format_exc())
                self.user_reply_statuses[chat_id].pop(user_id)
            except:
                logger.error("Произошла ошибка в работе Telegram бота.")
                logger.debug(traceback.format_exc())

        # Комманды
        @bot_instance.message_handler(commands=["add_chat"])
        def add_chat(message: types.Message):
            try:
                if message.chat.id in self.chat_ids:
                    self.bot.send_message(message.chat.id,
                                          "❌ Данный чат уже находится в списке чатов для уведомлений.")
                else:
                    self.chat_ids.append(message.chat.id)
                    telegram_tools.save_chat_ids(self.chat_ids)
                    self.bot.send_message(message.chat.id,
                                          "✔️ Теперь в этот чат будут приходить уведомления.")
            except:
                logger.error("Произошла ошибка в работе Telegram бота.")
                logger.debug(traceback.format_exc())

        @bot_instance.message_handler(commands=["remove_chat"])
        def remove_chat(message: types.Message):
            try:
                if message.chat.id not in self.chat_ids:
                    self.bot.send_message(message.chat.id,
                                          "❌ Данного чата нет в списке чатов для уведомлений.")
                else:
                    self.chat_ids.remove(message.chat.id)
                    telegram_tools.save_chat_ids(self.chat_ids)
                    self.bot.send_message(message.chat.id,
                                          "✔️ Теперь в этот чат не будут приходить уведомления.")
            except:
                logger.error("Произошла ошибка в работе Telegram бота.")
                logger.debug(traceback.format_exc())

        @bot_instance.message_handler(commands=["menu"])
        def show_menu(message: types.Message):
            try:
                self.bot.send_message(message.chat.id, "Меню", reply_markup=mainKeyboard)
            except:
                logger.error("Произошла ошибка в работе Telegram бота.")
                logger.debug(traceback.format_exc())

        @bot_instance.message_handler(func=lambda msg: msg.text == "📟 Команды 📟")
        def send_commands_text(message: types.Message):
            try:
                self.bot.send_message(message.chat.id, self.generate_help_text())
            except:
                logger.error("Произошла ошибка в работе Telegram бота.")
                logger.debug(traceback.format_exc())

        @bot_instance.message_handler(func=lambda msg: msg.text == "🤖 О боте 🤖")
        def send_about_text(message: types.Message):
            try:
                self.bot.send_message(message.chat.id, about_text)
            except:
                logger.error("Произошла ошибка в работе Telegram бота.")
                logger.debug(traceback.format_exc())

        @bot_instance.message_handler(func=lambda msg: msg.text == "📋 Логи 📋")
        def send_logs(message: types.Message):
            try:
                if not os.path.exists("logs/log.log"):
                    self.bot.send_message(message.chat.id, "❌ Лог файл не обнаружен.")
                else:
                    with open("logs/log.log", "r", encoding="utf-8") as f:
                        self.bot.send_document(message.chat.id, f)
            except:
                logger.error("Произошла ошибка в работе Telegram бота.")
                logger.debug(traceback.format_exc())

    def send_notification(self, text: str, replaces: list[list[str]] | None = None, reply_button=None):
        """
        Отправляет сообщение во все чаты для уведомлений из self.chat_ids
        :param text: текст уведомления.
        :param replaces: замены, которые нужно произвести ПОСЛЕ экранирования спец. символов.
        :param reply_button: экземпляр кнопки.
        """
        escape_characters = "_*[]()~`>#+-=|{}.!"
        for char in escape_characters:
            text = text.replace(char, f"\\{char}")

        if replaces:
            for i in replaces:
                text = text.replace(i[0], i[1])

        for chat_id in self.chat_ids:
            try:
                if reply_button is None:
                    self.bot.send_message(chat_id, text, parse_mode='MarkdownV2')
                else:
                    self.bot.send_message(chat_id, text, parse_mode='MarkdownV2', reply_markup=reply_button)
            except:
                logger.error("Произошла ошибка при отправке уведомления в Telegram.")
                logger.debug(traceback.format_exc())

    def generate_help_text(self) -> str:
        """
        Генерирует текст справки.

        :return: текст справки.
        """
        text = ""
        for module in self.commands_help:
            if not len(self.commands_help[module]):
                continue

            text += f"\n{module}\n"
            for command in self.commands_help[module]:
                text += f"    {command} - {self.commands_help[module][command]}\n"

        return text.strip()

    def add_command_help(self, plugin_name: str, command: str, help_text: str) -> None:
        """
        Добавляет справку о команде.

        :param plugin_name: имя плагина (лучше всего использовать переменную __name__).
        :param command: текст команды.
        :param help_text: текст справки.
        """
        if self.commands_help.get(plugin_name) is None:
            self.commands_help[plugin_name] = {}

        self.commands_help[plugin_name][command] = help_text

    def run(self):
        """
        Запускает поллинг.
        """
        try:
            logger.info(f"$CYANTelegram бот $YELLOW@{self.bot.user.username} $CYANзапущен.")
            self.bot.infinity_polling(logger_level=logging.DEBUG)
        except:
            logger.error("Произошла ошибка при получении обновлений Telegram (введен некорректный токен?).")
            logger.debug(traceback.format_exc())
