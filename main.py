import logging
import os
import sys
import colorama
from colorama import Fore, Back, Style
import traceback

import Utils.config_loader as cfg_loader
import Utils.logger
import Utils.exceptions as excs

from cardinal import Cardinal


CFG_LOADER_PREFIX = f"{Fore.YELLOW}{Back.RED}[Cfg loader]"
MAIN_PREFIX = f"{Back.RED}[Main]"
TRACEBACK_PREFIX = f"{Fore.BLACK}{Style.BRIGHT}[Traceback]"


def get_abs_path(path: str) -> str:
    """
    Возвращает полный путь. Проверяет, запущенно ли приложение как .exe файл или как python скрипт.
    :param path: путь до папки/файла.
    :return: Полный путь.
    """
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), path)
    else:
        return os.path.join(os.path.dirname(__file__), path)


# Инициируем цветной текст и логгер.
colorama.init()
if not os.path.exists("logs"):
    os.mkdir("logs")
Utils.logger.init_logger("FunPayBot", "logs/log.log")
logger = logging.getLogger("FunPayBot")
logger.debug("Новый запуск.")

# Загружаем конфиги
e = None
try:
    main_config_path = get_abs_path("configs/_main.cfg")
    MAIN_CONFIG = cfg_loader.load_main_config(main_config_path)
    logger.info("Обработал конфиг _main.cfg.")

    lots_config_path = get_abs_path("configs/lots.cfg")
    LOTS_CONFIG = cfg_loader.load_lots_config(lots_config_path)
    logger.info("Обработал конфиг lots.cfg.")

    auto_response_config_path = get_abs_path("configs/auto_response.cfg")
    AUTO_RESPONSE_CONFIG = cfg_loader.load_auto_response_config(auto_response_config_path)
    logger.info("Обработал конфиг auto_response.cfg.")

    auto_delivery_config_path = get_abs_path("configs/auto_delivery.cfg")
    AUTO_DELIVERY_CONFIG = cfg_loader.load_auto_delivery_config(auto_delivery_config_path)
    logger.info("Обработал конфиг auto_delivery.cfg.")

except (excs.ParamNotExists, excs.ParamValueEmpty, excs.ParamValueNotValid,
        excs.NoSuchTableError, excs.NoSuchColumnError, excs.NoProductsError,
        excs.NoProductVarError, excs.NoSuchProductFileError, excs.JSONParseError) as e:
    logger.error(e)
    logger.error("Завершаю программу...")
    exit()

except Exception as e:
    logger.critical("Произошло необработанное исключение.")
    traceback_text = traceback.format_exc()
    logger.debug(traceback_text)
    logger.error("Завершаю программу...")
    exit()

# Запускаем основную программу Cardinal
if __name__ == '__main__':
    main_program = Cardinal(
        MAIN_CONFIG,
        LOTS_CONFIG,
        AUTO_RESPONSE_CONFIG,
        AUTO_DELIVERY_CONFIG
    )
    main_program.init()
    main_program.run()