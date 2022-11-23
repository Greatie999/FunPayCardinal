import configparser
import codecs
import os
import sqlite3
import json

from .exceptions import (ParamNotExists, ParamValueEmpty, ParamValueNotValid,
                         NoSuchTableError, NoSuchColumnError, NoProductsError, NoProductVarError,
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


def check_db_table_exists(db_path: str, table_name: str) -> bool:
    """
    Проверяет существует ли таблица в файле базы данных.

    :param db_path: путь до файла базы данных.
    :param table_name: название таблицы.
    :return: True, если указанная таблица существует, False - если нет.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT * FROM sqlite_master WHERE type = 'table'")
    result = c.fetchall()
    c.close()
    conn.close()

    table_names = [table[1] for table in result]
    return table_name in table_names


def check_table_column_exists(db_path: str, table_name: str, column_name: str) -> bool:
    """
    Проверяет существует ли столбец в таблице базы данных.

    :param db_path: путь до файла базы данных.
    :param table_name: название таблицы.
    :param column_name: название столбца.
    :return: True, если указанный столбец существует, False - если нет.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute(f"PRAGMA table_info({table_name})")
    result = c.fetchall()
    c.close()
    conn.close()

    column_names = [column[1] for column in result]
    return column_name in column_names


def get_db_entries_count(db_path: str, table_name: str) -> int:
    """
    Возвращает количество записей в таблице table_name.
    :param db_path: путь до файла базы данных.
    :param table_name: название таблицы.
    :return: количество записей в таблице table_name
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(f"""SELECT COUNT(*) FROM {table_name}""")
    result = c.fetchall()[0][0]
    c.close()
    conn.close()
    return result


def load_main_config(config_path: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read_file(codecs.open(config_path, "r", "utf8"))
    return config


def load_lots_config(config_path: str) -> configparser.ConfigParser:
    """
    Парсит и проверяет на правильность конфиг лотов.

    :param config_path: путь до конфига лотов.
    :return: спарсеный конфиг лотов.
    """
    config = configparser.ConfigParser()
    config.read_file(codecs.open(config_path, "r", "utf8"))
    for alias in config.sections():
        check_param("name", alias, "lots.cfg", config[alias])
        check_param("exclude_auto_restore", alias, "lots.cfg",
                    config[alias], valid_values=["0", "1"], raise_ex_if_not_exists=False)
    return config


def load_auto_response_config(config_path: str) -> configparser.ConfigParser:
    """
    Парсит и проверяет на правильность конфиг команд.

    :param config_path: путь до конфига команд.
    :return: спарсеный конфиг команд.
    """
    config = configparser.ConfigParser()
    config.read_file(codecs.open(config_path, "r", "utf8"))
    for command in config.sections():
        check_param("response", command, "auto_response.cfg", config[command])
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

        # Проверяем указан параметр products_storage_type и если да, то правильно ли.
        products_storage_type = check_param("products_storage_type", lot, "auto_delivery.cfg",
                                            config[lot], raise_ex_if_not_exists=False)
        if products_storage_type is None:
            # Если данного параметра нет, то в текущем лоте более нечего проверять -> переход на след. итерацию.
            continue

        # Проверяем, есть ли хотя бы 1 переменная $product в тексте response.
        if "$product" not in lot_response:
            raise NoProductVarError(lot)

        # Проверяем указан ли параметр products_file_name и существует ли файл, указанный в этом параметре.
        products_file_path = check_param("products_file_path", lot, "auto_delivery.cfg", config[lot])
        if not os.path.exists(products_file_path):
            raise NoSuchProductFileError(lot, products_file_path)

        # Проверяем валидность данных в файле, указанном в products_file_name
        if products_storage_type == "json":
            with open(products_file_path, "r", encoding="utf-8") as f:
                products = f.read()
            try:
                products = json.loads(products)
            except json.decoder.JSONDecodeError as e:
                raise JSONParseError(lot, products_file_path, str(e))
            # Проверяем наличие товара
            if len(products) < 1:
                raise NoProductsError(products_file_path)

        elif products_storage_type == "db":
            # Проверяем указан ли параметр db_table_name и существует ли таблица с именем, указанным в этом параметре.
            db_table_name = check_param("db_table_name", lot, "auto_delivery.cfg", config[lot])
            check = check_db_table_exists(products_file_path, db_table_name)
            if not check:
                raise NoSuchTableError(products_file_path, db_table_name)

            # Проверяем указан ли параметр db_column_name и
            # существует ли столбец с именем, указанным в этом параметре, в таблице db_table_name.
            db_column_name = check_param("db_column_name", lot, "auto_delivery.cfg", config[lot])
            check = check_table_column_exists(products_file_path, db_table_name, db_column_name)
            if not check:
                raise NoSuchColumnError(products_file_path, db_table_name, db_column_name)

            if get_db_entries_count(products_file_path, db_table_name) < 1:
                raise NoProductsError(products_file_path)

    return config
