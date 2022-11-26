import json
import requests
from bs4 import BeautifulSoup
import logging

from .other import gen_rand_tag
from .account import Account
from .enums import Links, EventTypes


class Event:
    def __init__(self, e_type: EventTypes):
        self.type = e_type


class MessageEvent(Event):
    def __init__(self,
                 node_id: int,
                 message_text: str,
                 sender_username: str,
                 send_time: str | None,
                 tag: str | None):
        super(MessageEvent, self).__init__(EventTypes.NEW_MESSAGE)
        self.node_id = node_id
        self.sender_username = sender_username
        self.message_text = message_text
        self.send_time = send_time
        self.tag = tag


class OrderEvent(Event):
    def __init__(self, buyer: int, seller: int):
        super(OrderEvent, self).__init__(EventTypes.NEW_ORDER)
        self.buyer = buyer
        self.seller = seller


class Runner:
    def __init__(self, account: Account, timeout: float = 10.0):
        self.message_tag: str = gen_rand_tag()
        self.order_tag: str = gen_rand_tag()
        self.first_request = True

        self.account = account
        self.timeout = timeout

        self.last_messages: dict[int, MessageEvent] = {}
        self.processed_orders: dict[str, OrderEvent] = {}

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
                    send_time = msg.find("div", {"class": "contact-item-time"}).text

                    # Если это старое сообщение (сохранено в self.last_messages) -> пропускаем.
                    if node_id in self.last_messages:
                        check_msg = self.last_messages[node_id]
                        if check_msg.message_text == message_text and (
                                check_msg.send_time is not None and check_msg.send_time == send_time):
                            continue

                    sender_username = msg.find("div", {"class": "media-user-name"}).text

                    msg_object = MessageEvent(node_id=node_id, message_text=message_text, sender_username=sender_username,
                                              send_time=send_time, tag=self.message_tag)
                    self.last_messages[node_id] = msg_object
                    if self.first_request:
                        continue
                    events.append(msg_object)
            else:
                continue
        if self.first_request:
            self.first_request = False

        return events
