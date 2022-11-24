import os
import json
from colorama import Fore
from datetime import datetime

import FunPayAPI.account
import FunPayAPI.categories
import FunPayAPI.runner


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

    currency = account.currency if f" {account.currency}" is not None else ""

    greetings_text = f"""{greetings}, {Fore.CYAN}{account.username}.
Ваш ID: {Fore.YELLOW}{account.id}.
Ваш текущий баланс: {Fore.YELLOW}{account.balance}{currency}.
Текущие незавершенные сделки: {Fore.YELLOW}{account.active_sales}.
{Fore.MAGENTA}Удачной торговли!"""
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


def get_product_from_json(path: str) -> list[str, int] | None:
    with open(path, "r", encoding="utf-8") as f:
        products = f.read()

    products = json.loads(products)
    if not len(products):
        return None

    product = str(products[0])
    products.pop(0)
    amount = len(products)
    products = json.dumps(products, indent=4)

    with open(path, "w", encoding="utf-8") as f:
        f.write(products)
    return [product, amount]


def format_msg_text(text: str, msg: FunPayAPI.runner.MessageEvent):
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
