"""
В данном модуле написаны инструменты, которыми пользуется Кардинал в процессе своей работы.
"""


import os
import json
from datetime import datetime

import FunPayAPI.account
import FunPayAPI.categories
import FunPayAPI.runner
import FunPayAPI.orders

import Utils.exceptions as excs


def cache_categories(category_list: list[FunPayAPI.categories.Category]) -> None:
    """
    Кэширует данные о категориях аккаунта в файл storage/cache/categories.json. Необходимо для того, чтобы каждый раз
    при запуске бота не отправлять запросы на получение game_id каждой категории.

    :param category_list: список категорий, которые необходимо кэшировать.
    :return: None
    """
    result = {}
    for cat in category_list:
        # Если у объекта категории game_id = None, то и нет смысла кэшировать данную категорию.
        if cat.game_id is None:
            continue

        # Имя категории для кэширования = id категории_тип категории (lot - 0, currency - 1).
        # Например:
        # 146_0 = https://funpay.com/lots/146/
        # 146_1 = https://funpay.com/chips/146/
        category_cached_name = f"{cat.id}_{cat.type.value}"
        result[category_cached_name] = cat.game_id

    # Создаем папку для хранения кэшированных данных.
    if not os.path.exists("storage/cache"):
        os.makedirs("storage/cache")

    # Записываем данные в кэш.
    with open("storage/cache/categories.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(result, indent=4))


def load_cached_categories() -> dict:
    """
    Загружает данные о категориях аккаунта из файла storage/cache/categories.json. Необходимо для того, чтобы каждый раз
    при запуске бота не отправлять запросы на получение game_id каждой категории.

    :return: словарь загруженных категорий.
    """
    if not os.path.exists("storage/cache/categories.json"):
        return {}

    with open("storage/cache/categories.json", "r", encoding="utf-8") as f:
        cached_categories = f.read()

    try:
        cached_categories = json.loads(cached_categories)
    except json.decoder.JSONDecodeError:
        return {}
    return cached_categories


def create_greetings(account: FunPayAPI.account):
    """
    Генерирует приветствие для вывода в консоль после загрузки данных о пользователе.

    :return:
    """
    current_time = datetime.now()
    if current_time.hour < 4:
        greetings = "Какая прекрасная ночь"
    elif current_time.hour < 12:
        greetings = "Доброе утро"
    elif current_time.hour < 17:
        greetings = "Добрый день"
    elif current_time.hour < 24:
        greetings = "Добрый вечер"
    else:
        greetings = "Доброе утро"

    currency = f" {account.currency}" if account.currency is not None else ""

    greetings_text = f"""{greetings}, $CYAN{account.username}.
Ваш ID: $YELLOW{account.id}.
Ваш текущий баланс: $YELLOW{account.balance}{currency}.
Текущие незавершенные сделки: $YELLOW{account.active_orders}.
Удачной торговли!"""
    return greetings_text


def get_month_name(month_number: int) -> str:
    """
    Возвращает название месяца в родительном падеже.

    :param month_number: номер месяца.
    :return: название месяца в родительном падеже.
    """
    months = [
        "Января",
        "Февраля",
        "Марта",
        "Апреля",
        "Мая",
        "Июня",
        "Июля",
        "Августа",
        "Сентября",
        "Октября",
        "Ноября",
        "Декабря"
    ]
    if month_number > len(months):
        return months[0]
    return months[month_number-1]


def time_to_str(time_: int):
    """
    Конвертирует число в строку формата "Nч Nмин Nсек"

    :param time_: число для конвертации.
    :return: строку-время.
    """
    m = time_ // 60
    h = m // 60
    time_ -= m * 60
    m -= h * 60
    s = time_

    if not any([h, m, s]):
        return "0 сек"
    time_str = ""
    if h:
        time_str += f"{h}ч"
    if m:
        time_str += f" {m}мин"
    if s:
        time_str += f" {s}сек"
    return time_str.strip()


def get_product_from_json(path: str) -> list[str | int] | None:
    """
    Берет 1 единицу товара из файла.

    :param path: путь до файла с товарами.
    :return: [Товар, оставшееся кол-во товара]
    """
    with open(path, "r", encoding="utf-8") as f:
        products = f.read()

    products = json.loads(products)
    if not len(products):
        raise excs.NoProductsError(path)

    product = str(products[0])
    products.pop(0)
    amount = len(products)
    products = json.dumps(products, indent=4, ensure_ascii=False)

    with open(path, "w", encoding="utf-8") as f:
        f.write(products)
    return [product, amount]


def add_product_to_json(path: str, product: str) -> None:
    """
    Добавляет 1 единицу товара в файл.

    :param path: путь до файла с товарами.
    :param product: товар.
    :return:
    """
    with open(path, "r", encoding="utf-8") as f:
        products = f.read()

    products = json.loads(products)
    products.append(product)

    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(products, indent=4, ensure_ascii=False))


def format_msg_text(text: str, msg: FunPayAPI.runner.MessageEvent) -> str:
    """
    Форматирует текст, подставляя значения переменных, доступных для MessageEvent.

    :param text: текст для форматирования.
    :param msg: экземпляр MessageEvent.
    :return: форматированый текст.
    """
    date_obj = datetime.now()
    month_name = get_month_name(date_obj.month)
    date = date_obj.strftime("%d.%m.%Y")
    str_date = f"{date_obj.day} {month_name}"
    str_full_date = str_date + f" {date_obj.year} года"

    time_ = date_obj.strftime("%H:%M")
    time_full = date_obj.strftime("%H:%M:%S")

    variables = {
        "$full_date_text": str_full_date,
        "$date_text": str_date,
        "$date": date,
        "$time": time_,
        "$full_time": time_full,
        "$username": msg.sender_username,
        "$message_text": msg.message_text
    }

    for var in variables:
        text = text.replace(var, variables[var])
    return text


def format_order_text(text: str, order: FunPayAPI.orders.Order) -> str:
    """
    Форматирует текст, подставляя значения переменных, доступных для Order.

    :param text: текст для форматирования.
    :param order: экземпляр Order.
    :return: форматированый текст.
    """
    date_obj = datetime.now()
    month_name = get_month_name(date_obj.month)
    date = date_obj.strftime("%d.%m.%Y")
    str_date = f"{date_obj.day} {month_name}"
    str_full_date = str_date + f" {date_obj.year} года"

    time_ = date_obj.strftime("%H:%M")
    time_full = date_obj.strftime("%H:%M:%S")

    variables = {
        "$full_date_text": str_full_date,
        "$date_text": str_date,
        "$date": date,
        "$time": time_,
        "$full_time": time_full,
        "$username": order.buyer_name,
        "$order_name": order.title,
    }

    for var in variables:
        text = text.replace(var, variables[var])
    return text
