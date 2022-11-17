from dataclasses import dataclass
from bs4 import BeautifulSoup
import requests

from .enums import Links, OrderStatuses


@dataclass
class Order:
    id: str
    title: str
    price: float
    buyer_name: str
    buyer_id: int
    status: OrderStatuses


def get_orders(token: str,
               include_outstanding: bool = True,
               include_completed: bool = False,
               include_refund: bool = False) -> dict[str, Order]:
    """
    Получает данные о заказах на аккаунте.
    :param token: golden_key (токен) аккаунта.
    :param include_outstanding: искать незавершенные заказы.
    :param include_completed: искать завершенные заказы.
    :param include_refund: искать заказы, за которые оформлен возврат денежных средств.
    :return: Словарь {"id заказа": экземпляр дата-класса API.orders.Order}.
    """
    headers = {"cookie": f"golden_key={token}"}
    response = requests.get(Links.ORDERS, headers=headers)

    if response.status_code != 200:
        raise Exception  # todo: создать и добавить кастомное исключение: не удалось получить данные с сайта

    html_response = response.content.decode()
    parser = BeautifulSoup(html_response, "lxml")

    check_user = parser.find("div", {"class": "user-link-name"})
    if check_user is None:
        raise Exception  # todo: создать и добавить кастомное исключение: невалидный токен

    orders = parser.find_all("a", {"class": "tc-item"})
    parsed_orders = {}

    for i in orders:
        order_div_classname = i.get("class")
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

        order_id = i.find("div", {"class": "tc-order"}).text
        title = i.find("div", {"class": "order-desc"}).find("div").text
        price = float(i.find("div", {"class": "tc-price"}).text.split(" ")[0])

        buyer = i.find("div", {"class": "media-user-name"}).find("span")
        buyer_name = buyer.text
        buyer_id = int(buyer.get("data-href")[:-1].split("https://funpay.com/users/")[1])

        order_object = Order(id=order_id, title=title, price=price, buyer_name=buyer_name, buyer_id=buyer_id,
                             status=status)

        parsed_orders[order_id] = order_object

    return parsed_orders
