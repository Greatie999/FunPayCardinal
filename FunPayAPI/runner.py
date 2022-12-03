"""
В данном модуле написаны функции и классы, позволяющие отправлять запросы к FunPay с помощью FunPay runner'а.
"""


import json
import requests
from bs4 import BeautifulSoup
import logging

from .other import gen_rand_tag
from .account import Account
from .enums import Links, EventTypes


class Event:
    """
    Базовый класс для всех событий.
    """
    def __init__(self, e_type: EventTypes):
        """
        :param e_type: тип события.
        """
        self.type = e_type


class MessageEvent(Event):
    """
    Класс события нового сообщения.
    """
    def __init__(self,
                 node_id: int,
                 message_text: str,
                 sender_username: str | None,
                 tag: str | None):
        """
        :param node_id: ID чата.
        :param message_text: текст сообщения.
        :param sender_username: никнейм отправителя (название чата)
        :param tag: тэг runner'а.
        """
        super(MessageEvent, self).__init__(EventTypes.NEW_MESSAGE)
        self.node_id = node_id
        self.sender_username = sender_username
        self.message_text = message_text
        self.tag = tag


class OrderEvent(Event):
    """
     Класс события изменения в списке ордеров.
     """
    def __init__(self, buyer: int, seller: int):
        """
        :param buyer: кол-во покупок на аккаунте.
        :param seller: кол-во продаж на аккаунте.
        """
        super(OrderEvent, self).__init__(EventTypes.NEW_ORDER)
        self.buyer = buyer
        self.seller = seller


class Runner:
    """
    Класс runner'а.
    """
    def __init__(self, account: Account, timeout: float = 10.0):
        self.message_tag: str = gen_rand_tag()
        self.order_tag: str = gen_rand_tag()
        # Во время первого запроса все данные, полученные от FunPay не возвращаются в self.get_updates(), а сохраняются
        # внутри класса.
        self.first_request = True

        self.account = account
        self.timeout = timeout

        self.last_messages: dict[int, MessageEvent] = {}

        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())

    def get_updates(self) -> list[MessageEvent | OrderEvent]:
        """
        Получает список обновлений от FunPay.
        :return: список эвентов.
        """
        orders = {
            "type": "orders_counters",
            "id": self.account.id,
            "tag": self.order_tag,
            "data": False
        }
        chats = {
            "type": "chat_bookmarks",
            "id": self.account.id,
            "tag": self.message_tag,
            "data": False
        }
        payload = {
            "objects": json.dumps([orders, chats]),
            "request": False,
            "csrf_token": self.account.csrf_token
        }
        headers = {
            "accept": "*/*",
            "cookie": f"golden_key={self.account.golden_key}; PHPSESSID={self.account.session_id}",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest"
        }
        response = requests.post(Links.RUNNER, headers=headers, data=payload, timeout=self.timeout)
        json_response = response.json()
        self.logger.debug(json_response)
        events = []
        for obj in json_response["objects"]:
            if obj.get("type") == "orders_counters":
                self.order_tag = obj.get("tag")
                if not self.first_request:
                    info = obj.get("data")
                    order_obj = OrderEvent(info.get("buyer"), info.get("seller"))
                    events.append(order_obj)

            elif obj.get("type") == "chat_bookmarks":
                self.message_tag = obj.get("tag")
                self.account.chats_html = obj["data"]["html"]
                parser = BeautifulSoup(obj["data"]["html"], "lxml")
                messages = parser.find_all("a", {"class": "contact-item"})
                for msg in messages:
                    node_id = int(msg["data-id"])
                    message_text = msg.find("div", {"class": "contact-item-message"}).text

                    # Если это старое сообщение (сохранено в self.last_messages) -> пропускаем.
                    if node_id in self.last_messages:
                        check_msg = self.last_messages[node_id]
                        if check_msg.message_text == message_text:
                            continue

                    sender_username = msg.find("div", {"class": "media-user-name"}).text

                    msg_object = MessageEvent(node_id=node_id, message_text=message_text, sender_username=sender_username,
                                              tag=self.message_tag)
                    self.update_lat_message(msg_object)
                    if self.first_request:
                        continue
                    events.append(msg_object)
            else:
                continue
        if self.first_request:
            self.first_request = False

        return events

    def update_lat_message(self, msg: MessageEvent) -> None:
        """
        Вручную обновляет объект последнего сообщения в self.last_messages

        :param msg: экземпляр FunPayAPI.runner.MessageEvent
        """
        self.last_messages[msg.node_id] = msg
