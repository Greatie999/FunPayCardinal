import json
import requests
from bs4 import BeautifulSoup

from .other import gen_rand_tag
from .account import Account
from .enums import Links, EventTypes, OrderStatuses


class Event:
    def __init__(self, e_type: EventTypes):
        self.type = e_type


class MessageEvent(Event):
    def __init__(self,
                 node_id: int,
                 message_text: str,
                 sender_username: str,
                 send_time: str,
                 tag: str):
        super(MessageEvent, self).__init__(EventTypes.NEW_MESSAGE)
        self.node_id = node_id
        self.sender_username = sender_username
        self.message_text = message_text
        self.send_time = send_time
        self.tag = tag


class OrderEvent(Event):
    def __init__(self,
                 id_: str,
                 title: str,
                 price: float,
                 buyer_username: str,
                 buyer_id: int,
                 status: OrderStatuses):
        super(OrderEvent, self).__init__(EventTypes.NEW_ORDER)
        self.id = id_
        self.title = title
        self.price = price
        self.buyer_name = buyer_username
        self.buyer_id = buyer_id
        self.status = status


class Runner:
    def __init__(self, account: Account, timeout: float = 10.0):
        self.message_tag: str = gen_rand_tag()
        self.order_tag: str = gen_rand_tag()
        self.first_request = True

        self.account = account
        self.timeout = timeout

        self.last_messages: dict[int, MessageEvent] = {}
        self.processed_orders: dict[str, OrderEvent] = {}

    def get_updates(self) -> list[MessageEvent, OrderEvent]:
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
        events = []
        for obj in json_response["objects"]:
            if obj.get("type") == "orders_counters":
                self.order_tag = obj.get("tag")

            elif obj.get("type") == "chat_bookmarks":
                self.message_tag = obj.get("tag")
                parser = BeautifulSoup(obj["data"]["html"], "lxml")
                messages = parser.find_all("a", {"class": "contact-item"})
                for msg in messages:
                    node_id = int(msg["data-id"])
                    message_text = msg.find("div", {"class": "contact-item-message"}).text
                    send_time = msg.find("div", {"class": "contact-item-time"}).text

                    # Если это старое сообщение (сохранено в self.last_messages) -> пропускаем.
                    if node_id in self.last_messages:
                        check_msg = self.last_messages[node_id]
                        if check_msg.message_text == message_text and check_msg.send_time == send_time:
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
