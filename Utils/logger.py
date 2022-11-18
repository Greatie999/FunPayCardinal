import re
from colorama import Fore, Back, Style
from datetime import datetime
import logging
import os
from enum import Enum


MAX_PREFIX_LENGTH = 14


class LogTypes(Enum):
    DONE = Fore.GREEN
    WARN = Fore.YELLOW
    ERROR = Fore.RED
    TRACEBACK = Fore.BLACK + Style.BRIGHT
    NEUTRAL = Fore.WHITE


class Logger:
    def __init__(self, to_file: bool = True):
        self.__prefix = f"{Back.LIGHTBLACK_EX}[LOGGER]"
        self.to_file = to_file
        self.log_file_name = datetime.now().strftime("%d-%m-%Y-%H-%M-%S.txt")
        if self.to_file:
            if not os.path.exists("logs"):
                os.mkdir("logs")
            logging.basicConfig(filename=f"logs\\{self.log_file_name}", encoding="utf-8", level=logging.INFO)

        self.logs = []
        self.last_log = ""
        self.printing = False
        self.clear_expression = re.compile(r"(\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]))|(\n)|(\r)")

        self.log("Логгер успешно инициализирован.", self.__prefix)

    def log(self, text: str, prefix: str, log_type: LogTypes = LogTypes.DONE) -> None:
        """
        Добавляет лог в очередь. В последствии будет выведен в консоль и сохранен в файл с помощью Logger.__print_logs()
        Формат лога: [Номер аккаунта][Время]  [Префикс]  Текст лога
        :param text: Основной текст лога.
        :param prefix: Префикс (имя) модуля, откуда пришел лог.
        :param log_type: Тип лога. Значение от 0 до 4.
        :return: None
        """

        row_prefix = self.clear_text(prefix)
        pre_space = int((MAX_PREFIX_LENGTH - len(row_prefix)) / 2)
        post_space = MAX_PREFIX_LENGTH - len(row_prefix) - pre_space
        prefix = f"{' ' * pre_space}{prefix}{Style.RESET_ALL}{' ' * post_space}"

        self.logs.append(f"{Fore.LIGHTBLACK_EX}[{datetime.now().strftime('%d-%m-%Y %H:%M:%S.%f')[:-3]}]{Style.RESET_ALL}"
                         f"{prefix}"
                         f"{log_type.value}{text.replace('$color', str(log_type.value))}{Style.RESET_ALL}")
        self.__print_logs()

    def clear_text(self, text: str) -> str:
        """
        Убирает из текста все ANSI ESC символы (цвета и т.д.), а так же символы для работы с кареткой (\n, \r).
        :param text: Строка, которую необходимо очистить.
        :return: Строку без ANSI ESC символов и без символов для работы с кареткой.
        """
        return self.clear_expression.sub("", text)

    def __print_logs(self) -> None:
        """
        Выводит в консоль и добавляет в файл логи из self.logs.
        :return: None
        """
        if self.printing:
            return
        self.printing = True
        if len(self.logs):
            for _ in self.logs:
                text = self.logs.pop(0)
                if "\r" in text:
                    print(text, end="")
                elif "\r" not in text and "\r" in self.last_log:
                    print(f"\n{text}")
                else:
                    print(text)
                self.last_log = text
                if self.to_file:
                    logging.info(self.clear_text(text))
        self.printing = False
