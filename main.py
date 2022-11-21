import os
import sys
import colorama
from colorama import Fore, Back, Style
import traceback

import Utils.config_loader as cfg_loader
from Utils.logger import Logger, LogTypes
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
logger = Logger()

# Загружаем конфиги
e = None
try:
    main_config_path = get_abs_path("configs/_main.cfg")
    MAIN_CONFIG = cfg_loader.load_main_config(main_config_path)
    logger.log("Обработал конфиг _main.cfg.", CFG_LOADER_PREFIX)

    lots_config_path = get_abs_path("configs/lots.cfg")
    LOTS_CONFIG = cfg_loader.load_lots_config(lots_config_path)
    logger.log("Обработал конфиг lots.cfg.", CFG_LOADER_PREFIX)

    auto_response_config_path = get_abs_path("configs/auto_response.cfg")
    AUTO_RESPONSE_CONFIG = cfg_loader.load_auto_response_config(auto_response_config_path)
    logger.log("Обработал конфиг auto_response.cfg.", CFG_LOADER_PREFIX)

    auto_delivery_config_path = get_abs_path("configs/auto_delivery.cfg")
    AUTO_DELIVERY_CONFIG = cfg_loader.load_auto_delivery_config(auto_delivery_config_path)
    logger.log("Обработал конфиг auto_delivery.cfg.", CFG_LOADER_PREFIX)

except (excs.ParamNotExists, excs.ParamValueEmpty, excs.ParamValueNotValid,
        excs.NoSuchTableError, excs.NoSuchColumnError, excs.NoProductsError,
        excs.NoProductVarError, excs.NoSuchProductFileError, excs.JSONParseError) as e:
    for line in str(e).split("\n"):
        logger.log(line, CFG_LOADER_PREFIX, LogTypes.ERROR)
    logger.log("Завершаю программу...", MAIN_PREFIX, LogTypes.WARN)
    exit()

except Exception as e:
    logger.log("Произошло необработанное исключение.", MAIN_PREFIX, LogTypes.ERROR)
    traceback_text = traceback.format_exc()
    for line in traceback_text.split("\n"):
        if not line:
            continue
        logger.log(line, TRACEBACK_PREFIX, LogTypes.TRACEBACK)
    logger.log("Завершаю программу...", MAIN_PREFIX, LogTypes.WARN)
    exit()

# Запускаем основную программу Cardinal
main_program = Cardinal(
    MAIN_CONFIG,
    LOTS_CONFIG,
    AUTO_RESPONSE_CONFIG,
    AUTO_DELIVERY_CONFIG,
    logger)
main_program.init()
main_program.run()