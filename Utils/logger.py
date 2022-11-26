import re
import logging
import logging.handlers
from colorama import Fore, Back, Style


def add_colors(text: str) -> str:
    colors = {
        "$YELLOW": Fore.YELLOW,
        "$CYAN": Fore.CYAN,
        "$MAGENTA": Fore.MAGENTA,
        "$BLUE": Fore.BLUE,
    }
    for c in colors:
        text = text.replace(c, colors[c])
    return text


class CLILoggerFormatter(logging.Formatter):
    """
    Форматтер для вывода логов в консоль.
    """
    log_format = f"{Fore.BLACK + Style.BRIGHT}[%(asctime)s]{Style.RESET_ALL}" \
                 f"{Fore.CYAN}>{Style.RESET_ALL} $color%(levelname)s:$spaces %(message)s{Style.RESET_ALL}"

    colors = {
        logging.DEBUG: Fore.BLACK + Style.BRIGHT,
        logging.INFO: Fore.GREEN,
        logging.WARN: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Back.RED
    }

    time_format = "%Y-%m-%d %H:%M:%S"
    max_level_name_length = 10

    def __init__(self):
        super(CLILoggerFormatter, self).__init__()

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        msg = add_colors(msg)
        msg = msg.replace("$color", self.colors[record.levelno])
        record.msg = msg
        log_format = self.log_format.replace("$color", self.colors[record.levelno])\
            .replace("$spaces", " " * (self.max_level_name_length - len(record.levelname)))
        formatter = logging.Formatter(log_format, self.time_format)
        return formatter.format(record)


class FileLoggerFormatter(logging.Formatter):
    """
    Форматтер для сохранения логов в файл.
    """
    log_format = "[%(asctime)s][%(filename)s][%(funcName)s][%(lineno)d]> %(levelname)s: %(message)s"
    max_level_name_length = 12
    clear_expression = re.compile(r"(\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]))|(\n)|(\r)")

    def __init__(self):
        super(FileLoggerFormatter, self).__init__()

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        msg = self.clear_expression.sub("", msg)
        record.msg = msg
        formatter = logging.Formatter(self.log_format)
        return formatter.format(record)


CONFIG = {
    "version": 1,
    "handlers": {
        "file_handler": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "level": "DEBUG",
            "formatter": "file_formatter",
            "filename": "logs/log.log",
            "when": "midnight",
            "encoding": "utf-8"
        },

        "cli_handler": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "cli_formatter"
        }
    },

    "formatters": {
        "file_formatter": {
            "()": "Utils.logger.FileLoggerFormatter"
        },

        "cli_formatter": {
            "()": "Utils.logger.CLILoggerFormatter"
        }
    },

    "loggers": {
        "main": {
            "handlers": ["cli_handler", "file_handler"],
            "level": "DEBUG"
        },
        "FunPayAPI": {
            "handlers": ["cli_handler", "file_handler"],
            "level": "DEBUG"
        },
        "Cardinal": {
            "handlers": ["cli_handler", "file_handler"],
            "level": "DEBUG"
        },
        "TGBot": {
            "handlers": ["cli_handler", "file_handler"],
            "level": "DEBUG"
        },
        "TeleBot": {
            "handlers": ["file_handler"],
            "level": "ERROR",
            "propagate": "False"
        }
    }
}
