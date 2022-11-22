"""
Модуль с разными инструментами для работы других модулей.
"""


import string
import random


def get_wait_time_from_raise_response(response: str) -> int:
    """
    Парсит ответ FunPay на запрос о поднятии лотов.
    :param response: текст ответа.
    :return: Примерное время ожидание до следующего поднятия лотов (в секундах).
    """
    if "сек" in response:
        response = response.split()
        return int(response[1])
    elif "минуту." in response:
        return 60
    elif "мин" in response:
        response = response.split()
        # ["Подождите", "n", "минут."]
        return (int(response[1])-1) * 60
    elif "час" in response:
        return 3600
    else:
        return 10


def gen_rand_tag() -> str:
    """
    Генерирует случайный тег для запроса (для runner'a)
    :return: сгенерированный тег
    """
    simbols = string.digits + string.ascii_lowercase
    tag = "".join(random.choice(simbols) for _ in range(10))
    return tag
