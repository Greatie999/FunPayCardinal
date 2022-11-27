import configparser
import codecs
import os
import json

from Utils.exceptions import (SectionNotExists, ParamNotExists, ParamValueEmpty, ParamValueNotValid,
                              NoProductsError, NoProductVarError,
                              NoSuchProductFileError, JSONParseError)


def check_param(param_name: str,
                section_name: str,
                config_name: str,
                obj: dict | configparser.SectionProxy,
                valid_values: list[str, None] | None = None,
                raise_ex_if_not_exists: bool = True) -> str | None:
    """
    Проверяет, существует ли в переданном словаре указанный ключ, и если да, валидно ли его значение (перед проверкой
    значение проходит через .strip()).
    Если нет - райзит исключение.

    :param param_name: название ключа.
    :param section_name: название секции (для исключений).
    :param config_name: название конфига (для исключений).
    :param obj: словарь.
    :param valid_values: список валидных значений. Если не указан, любая непустая строка - валидное значение.
    :param raise_ex_if_not_exists: райзить ли исключение, если параметр не обнаружен
    (если параметр опционален, например).

    :raise ParamNotExists: если ключ отсутствует.
    :raise ParamValueEmpty: если значения ключа пустое и raise_ex_if_not_exists == True.
    :raise ParamValueNotValid: если значение ключа невалидно.

    :return: Значение ключа, если ключ найден и его значение валидно. Если ключ не найден и
    raise_ex_if_not_exists == False - возвращает None. В любом другом случае райзит исключения.
    """
    value = obj.get(param_name)
    if value is None:
        if raise_ex_if_not_exists:
            raise ParamNotExists(section_name, param_name, config_name)
        return value

    value = value.strip()
    if not value:
        raise ParamValueEmpty(section_name, param_name, config_name)

    if valid_values is not None:
        if value not in valid_values:
            raise ParamValueNotValid(section_name, param_name, valid_values, config_name)

    return value


def load_main_config(config_path: str) -> configparser.ConfigParser:
    """
    Парсит и проверяет на правильность основной конфиг.
    :param config_path: путь до основного конфига.
    :return: спарсеный основной конфиг.
    """
    config = configparser.ConfigParser()
    config.read_file(codecs.open(config_path, "r", "utf8"))

    values = {
        "FunPay": {
            "golden_key": "any",
            "autoRaise": ["0", "1"],
            "autoResponse": ["0", "1"],
            "autoDelivery": ["0", "1"],
            "autoRestore": ["0", "1"]
        },
        "Telegram": {
            "enabled": ["0", "1"],
            "token": "any",
            "secretKey": "any",
            "lotsRaiseNotification": ["0", "1"],
            "productsDeliveryNotification": ["0", "1"],
            "newMessageNotification": ["0", "1"]
        },
        "Other": {
            "botName": "any"

        }
    }

    for section in values:
        if section not in config.sections():
            raise SectionNotExists(section, "_main.cfg")

        for param in values[section]:
            if values[section][param] == "any":
                check_param(param, section, "_main.cfg", config[section])
            else:
                check_param(param, section, "_main.cfg", config[section], valid_values=values[section][param])
    return config


def load_lots_config(config_path: str) -> configparser.ConfigParser:
    """
    Парсит и проверяет на правильность конфиг лотов.

    :param config_path: путь до конфига лотов.
    :return: спарсеный конфиг лотов.
    """
    config = configparser.ConfigParser()
    config.read_file(codecs.open(config_path, "r", "utf8"))
    for lot in config.sections():
        check_param("exclude_auto_restore", lot, "lots.cfg",
                    config[lot], valid_values=["0", "1"], raise_ex_if_not_exists=False)
    return config


def load_auto_response_config(config_path: str) -> configparser.ConfigParser:
    """
    Парсит и проверяет на правильность конфиг команд.

    :param config_path: путь до конфига команд.
    :return: спарсеный конфиг команд.
    """
    config = configparser.ConfigParser()
    config.read_file(codecs.open(config_path, "r", "utf8"))
    multi_commands = []
    for command in config.sections():
        check_param("response", command, "auto_response.cfg", config[command])
        check_param("telegramNotification", command, "auto_response.cfg", config[command],
                    valid_values=["0", "1"], raise_ex_if_not_exists=False)
        check_param("notificationText", command, "auto_response.cfg", config[command], raise_ex_if_not_exists=False)

        # Если в названии команды есть "|" - значит это несколько команд.
        if "|" in command:
            multi_commands.append(command)

    for commands in multi_commands:
        copy_obj = config[commands]
        cmds = commands.split("|")

        for cmd in cmds:
            config.add_section(cmd.strip())
            for param in copy_obj:
                config.set(cmd.strip(), param, copy_obj[param])
        config.remove_section(commands)

    return config


def load_auto_delivery_config(config_path: str) -> configparser.ConfigParser:
    """
    Парсит и проверяет на правильность конфиг авто-выдачи.

    :param config_path: путь до конфига авто-выдачи.
    :return: спарсеный конфиг товаров для авто-выдачи.
    """
    config = configparser.ConfigParser()
    config.read_file(codecs.open(config_path, "r", "utf8"))

    for lot in config.sections():
        # Проверяем обязательный параметр response.
        lot_response = check_param("response", lot, "auto_delivery.cfg", config[lot])

        # Проверяем указан параметр productsFilePath.
        products_file_path = check_param("productsFilePath", lot, "auto_delivery.cfg",
                                         config[lot], raise_ex_if_not_exists=False)
        if products_file_path is None:
            # Если данного параметра нет, то в текущем лоте более нечего проверять -> переход на след. итерацию.
            continue

        # Проверяем, существует ли файл.
        if not os.path.exists(products_file_path):
            raise NoSuchProductFileError(lot, products_file_path)

        # Проверяем валидность json'а.
        with open(products_file_path, "r", encoding="utf-8") as f:
            products = f.read()
        try:
            products = json.loads(products)
        except json.decoder.JSONDecodeError as e:
            raise JSONParseError(lot, products_file_path, str(e))

        # Проверяем кол-во товара
        if len(products) < 1:
            raise NoProductsError(products_file_path)

        # Проверяем, есть ли хотя бы 1 переменная $product в тексте response.
        if "$product" not in lot_response:
            raise NoProductVarError(lot)

    return config
