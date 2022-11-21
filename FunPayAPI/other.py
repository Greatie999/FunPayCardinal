"""
Модуль с разными инструментами для работы других модулей.
"""


def get_wait_time_from_raise_response(response: str):
    """
    Парсит ответ FunPay на запрос о поднятии лотов.
    :param response: текст ответа.
    :return: Примерное время ожидание до следующего поднятия лотов (в секундах).
    """
    if "сек" in response:
        response = response.split()
        return int(response[1]) + 2
    elif "минуту" in response:
        return 70
    elif "мин" in response:
        response = response.split()
        # ["Подождите", "n", "минут."]
        return (int(response[1])-1) * 60 + 2
    elif "час" in response:
        return 3600
    else:
        return 10
