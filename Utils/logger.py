import re
import logging
import logging.handlers
from colorama import Fore, Back, Style


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


def init_logger(name: str, log_path: str) -> None:
    """
    Создает логгер.
    :param name: название логгера.
    :param log_path: путь до файла с логами.
    :return:
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    cli_handler = logging.StreamHandler()
    cli_handler.setFormatter(CLILoggerFormatter())
    cli_handler.setLevel(logging.INFO)
    logger.addHandler(cli_handler)

    file_handler = logging.handlers.TimedRotatingFileHandler(filename=log_path, when="midnight", encoding="utf-8")
    file_handler.setFormatter(FileLoggerFormatter())
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
