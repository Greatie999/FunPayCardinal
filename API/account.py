from dataclasses import dataclass
from bs4 import BeautifulSoup
import requests
import json
import time

from .enums import Links


@dataclass(frozen=True)
class Account:
    """
    Датакласс, описывающий аккаунт. Возвращается API.account.get_account_data(token).\n
    app_data: dict - словарь с данными из <body data-app-data=>
    id: int - id пользователя.\n
    username: str - имя пользователя.\n
    balance: float - текущий баланс пользователя.\n
    active_sales: int - текущие активные продажи пользователя.\n
    csrf_token: str - csrf токен.\n
    session_id: str - PHPSESSID.\n
    last_update: int - время последнего обновления.
    """
    app_data: dict
    id: int
    username: str
    balance: float
    active_sales: int
    csrf_token: str
    session_id: str
    last_update: int


def get_account_data(token: str) -> Account:
    """
    Возвращает данные аккаунта FunPay.
    :param token: golden_key (токен) аккаунта.
    :return: Словарь с данными, если запрос прошел успешно.
    Словарь с описанием ошибки - если нет.
    Формат данных: {"success": True / False, "data": {}}
    где "success" - результат выполнения, "data": - полученные с сервера данные / описание ошибки.
    """
    headers = {"cookie": f"golden_key={token}"}
    response = requests.get(Links.BASE_URL, headers=headers)

    if response.status_code != 200:
        raise Exception  # todo: создать и добавить кастомное исключение: не удалось получить данные с сайта

    html_response = response.content.decode()
    parser = BeautifulSoup(html_response, "lxml")

    username = parser.find("div", {"class": "user-link-name"})
    if username is None:
        raise Exception  # todo: создать и добавить кастомное исключение: невалидный токен
    username = username.text

    app_data = json.loads(parser.find("body")["data-app-data"])
    userid = app_data["userId"]
    csrf_token = app_data["csrf-token"]

    active_sales = parser.find("span", {"class": "badge badge-trade"})
    active_sales = int(active_sales.text) if active_sales else 0

    balance = parser.find("span", {"class": "badge badge-balance"})
    balance = float(balance.text.split(" ")[0]) if balance else 0

    cookies = response.cookies.get_dict()
    session_id = cookies["PHPSESSID"]

    return Account(app_data=app_data, id=userid, username=username, balance=balance, active_sales=active_sales,
                   csrf_token=csrf_token, session_id=session_id, last_update=int(time.time()))
