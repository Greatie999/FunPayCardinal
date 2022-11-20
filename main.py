import os
import sys
import colorama

import Utils.config_loader as cfg_loader
from Utils.logger import Logger


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


colorama.init()
logger = Logger()

try:
    main_config_path = get_abs_path("configs/_main.cfg")
    MAIN_CONFIG = cfg_loader.load_main_config(main_config_path)
except Exception:
    pass  # todo: сделать обработку разных исключений.

try:
    lots_config_path = get_abs_path("configs/lots.cfg")
    LOTS_CONFIG = cfg_loader.load_lots_config(lots_config_path)
except Exception:
    pass  # todo: сделать обработку разных исключений.

try:
    auto_response_config_path = get_abs_path("configs/auto_response.cfg")
    AUTO_RESPONSE_CONFIG = cfg_loader.load_auto_response_config(auto_response_config_path)
except Exception:
    pass  # todo: сделать обработку разных исключений.

try:
    auto_delivery_config_path = get_abs_path("configs/auto_delivery.cfg")
    AUTO_DELIVERY_CONFIG = cfg_loader.load_auto_response_config(auto_delivery_config_path)
except Exception:
    pass  # todo: сделать обработку разных исключений.
