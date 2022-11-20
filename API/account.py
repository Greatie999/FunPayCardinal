from bs4 import BeautifulSoup
import requests
import json
import time

from .enums import Links, OrderStatuses, CategoryTypes
from .orders import Order


class Account:
    """
    Класс, описывающий аккаунт. Возвращается API.account.get_account_data(token).
    """
    def __init__(self, app_data: dict, id_: int, username: str, balance: float, currency: str | None,
                 active_sales: int, csrf_token: str, session_id: str, last_update: int):
        """
        :param app_data: словарь с данными из <body data-app-data=>
        :param id_: id пользователя.
        :param username: имя пользователя.
        :param balance: текущий баланс пользователя.
        :param currency: знак валюты на аккаунте.
        :param active_sales: текущие активные продажи пользователя.
        :param csrf_token: csrf токен.
        :param session_id: PHPSESSID.
        :param last_update: время последнего обновления.
        """
        self.app_data = app_data
        self.id = id_
        self.username = username
        self.balance = balance
        self.currency = currency
        self.active_sales = active_sales
        self.csrf_token = csrf_token
        self.session_id = session_id
        self.last_update = last_update


def get_account_data(token: str, timeout: float = 10.0) -> Account:
    """
    Получает общие данные аккаунта FunPay.

    :param token: golden_key (токен) аккаунта.
    :param timeout: тайм-аут выполнения запроса.
    :return: Экземпляр дата-класса API.account.Account
    """
    headers = {"cookie": f"golden_key={token}"}

    response = requests.get(Links.BASE_URL, headers=headers, timeout=timeout)
    if response.status_code != 200:
        raise Exception  # todo: создать и добавить кастомное исключение: не удалось получить данные с сайта.

    html_response = response.content.decode()
    parser = BeautifulSoup(html_response, "lxml")

    username = parser.find("div", {"class": "user-link-name"})
    if username is None:
        raise Exception  # todo: создать и добавить кастомное исключение: невалидный токен.
    username = username.text

    app_data = json.loads(parser.find("body")["data-app-data"])
    userid = app_data["userId"]
    csrf_token = app_data["csrf-token"]

    active_sales = parser.find("span", {"class": "badge badge-trade"})
    active_sales = int(active_sales.text) if active_sales else 0

    balance = parser.find("span", {"class": "badge badge-balance"})
    balance_count = float(balance.text.split(" ")[0]) if balance else 0
    balance_currency = balance.text.split(" ")[1] if balance else None

    cookies = response.cookies.get_dict()
    session_id = cookies["PHPSESSID"]

    return Account(app_data=app_data, id_=userid, username=username, balance=balance_count, currency=balance_currency,
                   active_sales=active_sales,
                   csrf_token=csrf_token, session_id=session_id, last_update=int(time.time()))


def get_account_orders(token: str,
                       session_id: str | None = None,
                       include_outstanding: bool = True,
                       include_completed: bool = False,
                       include_refund: bool = False,
                       exclude: list[int] | None = None,
                       timeout: float = 10.0) -> dict[str, Order]:
    """
    Получает список заказов на аккаунте.

    :param token: golden_key (токен) аккаунта.
    :param session_id: PHPSESSID.
    :param include_outstanding: включить в список оплаченные (но не завершенные) заказы.
    :param include_completed: включить в список завершенные заказы.
    :param include_refund: включить в список заказы, за которые оформлен возврат.
    :param exclude: список ID заказов, которые нужно исключить из итогового списка.
    :param timeout: тайм-аут выполнения запроса.
    :return: Словарь {id заказа (int): экземпляр дата-класса API.orders.Order}.
    """
    exclude = exclude if exclude else []
    headers = {"cookie": f"golden_key={token};"}
    if session_id:
        headers["cookie"] += f" PHPSESSID={session_id};"

    response = requests.get(Links.ORDERS, headers=headers, timeout=timeout)
    if response.status_code != 200:
        raise Exception  # todo: создать и добавить кастомное исключение: не удалось получить данные с сайта.

    html_response = response.content.decode()
    parser = BeautifulSoup(html_response, "lxml")

    check_user = parser.find("div", {"class": "user-link-name"})
    if check_user is None:
        raise Exception  # todo: создать и добавить кастомное исключение: невалидный токен.

    order_divs = parser.find_all("a", {"class": "tc-item"})
    parsed_orders = {}

    for div in order_divs:
        order_div_classname = div.get("class")
        if "warning" in order_div_classname:
            if not include_refund:
                continue
            status = OrderStatuses.REFUND
        elif "info" in order_div_classname:
            if not include_outstanding:
                continue
            status = OrderStatuses.OUTSTANDING
        else:
            if not include_completed:
                continue
            status = OrderStatuses.COMPLETED

        order_id = div.find("div", {"class": "tc-order"}).text
        if order_id in exclude:
            continue
        title = div.find("div", {"class": "order-desc"}).find("div").text
        price = float(div.find("div", {"class": "tc-price"}).text.split(" ")[0])

        buyer = div.find("div", {"class": "media-user-name"}).find("span")
        buyer_name = buyer.text
        buyer_id = int(buyer.get("data-href")[:-1].split("https://funpay.com/users/")[1])

        order_object = Order(id_=order_id, title=title, price=price, buyer_username=buyer_name, buyer_id=buyer_id,
                             status=status)

        parsed_orders[order_id] = order_object

    return parsed_orders


def get_game_id_by_category_id(token: str, category_id: int, category_type: CategoryTypes,
                               timeout: float = 10.0) -> int:
    """
    Получает ID игры, к которой относится категория.

    :param token: golden_key (токен) аккаунта.
    :param category_id: ID категории, ID игры которой нужно получить.
    :param category_type: тип категории.
    :param timeout: тайм-аут выполнения запроса.
    :return: ID игры, к которой относится категория.
    """
    if category_type == CategoryTypes.LOT:
        link = f"{Links.BASE_URL}/lots/{category_id}/trade"
    else:
        link = f"{Links.BASE_URL}/chips/{category_id}/trade"

    headers = {"cookie": f"golden_key={token}"}
    response = requests.get(link, headers=headers, timeout=timeout)
    if response.status_code == 404:
        raise Exception  # todo: создать и добавить кастомное исключение: категория не найдена.
    if response.status_code != 200:
        raise Exception  # todo: создать и добавить кастомное исключение: не удалось получить данные с сайта.

    html_response = response.content.decode()
    parser = BeautifulSoup(html_response, "lxml")

    check_user = parser.find("div", {"class": "user-link-name"})
    if check_user is None:
        raise Exception  # todo: создать и добавить кастомное исключение: невалидный токен.

    if category_type == CategoryTypes.LOT:
        game_id = int(parser.find("div", {"class": "col-sm-6"}).find("button")["data-game"])
    else:
        game_id = int(parser.find("input", {"name": "game"})["value"])

    return game_id
