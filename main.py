import logging.config
import os
import sys
import colorama
import traceback

import Utils.config_loader as cfg_loader
from Utils.logger import CONFIG
import Utils.exceptions as excs

from cardinal import Cardinal


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
logging.config.dictConfig(CONFIG)
logger = logging.getLogger("main")
logger.debug("Новый запуск.")

# Загружаем конфиги
e = None
try:
    main_config_path = get_abs_path("configs/_main.cfg")
    MAIN_CONFIG = cfg_loader.load_main_config(main_config_path)
    logger.info("$MAGENTAОбработал конфиг _main.cfg.")

    # Временно отключено.
    #lots_config_path = get_abs_path("configs/lots.cfg")
    #LOTS_CONFIG = cfg_loader.load_lots_config(lots_config_path)
    #logger.info("$MAGENTAОбработал конфиг lots.cfg.")

    auto_response_config_path = get_abs_path("configs/auto_response.cfg")
    AUTO_RESPONSE_CONFIG = cfg_loader.load_auto_response_config(auto_response_config_path)
    logger.info("$MAGENTAОбработал конфиг auto_response.cfg.")

    auto_delivery_config_path = get_abs_path("configs/auto_delivery.cfg")
    AUTO_DELIVERY_CONFIG = cfg_loader.load_auto_delivery_config(auto_delivery_config_path)
    logger.info("$MAGENTAОбработал конфиг auto_delivery.cfg.")

except (excs.SectionNotExists, excs.ParamNotExists, excs.ParamValueEmpty, excs.ParamValueNotValid,
        excs.NoProductsError, excs.NoProductVarError,
        excs.NoSuchProductFileError, excs.JSONParseError) as e:
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
    try:
        main_program = Cardinal(
            MAIN_CONFIG,
            # LOTS_CONFIG,
            AUTO_RESPONSE_CONFIG,
            AUTO_DELIVERY_CONFIG
        )
        main_program.init()
        main_program.run()
    except:
        logger.critical("Произошла наикритическая ошибка, которая добила меня окончательно...")
        logger.critical("Срочно отправь лог файл разработчику!")
        logger.debug(traceback.format_exc())
        exit()