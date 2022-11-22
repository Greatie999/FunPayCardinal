import json
import requests
from typing import Callable
from bs4 import BeautifulSoup

from .other import gen_rand_tag
from .account import Account
from .enums import Links


class Message:
    def __init__(self, node_id: int, message_text: str, sender_username: str, send_time: str, tag: str):
        self.node_id = node_id
        self.sender_username = sender_username
        self.message_text = message_text
        self.send_time = send_time
        self.tag = tag


class Runner:
    def __init__(self, account: Account, timeout: float = 10.0):
        self.new_message_event_handlers: list[Callable] = []
        self.new_order_event_handlers: list[Callable] = []

        self.message_tag: str = gen_rand_tag()
        self.order_tag: str = gen_rand_tag()
        self.first_request = True

        self.account = account
        self.timeout = timeout

        self.last_messages: dict[int, Message] = {}

    def get_updates(self):
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
        print(json_response)
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

                    msg_object = Message(node_id=node_id, message_text=message_text, sender_username=sender_username,
                                         send_time=send_time, tag=self.message_tag)
                    self.last_messages[node_id] = msg_object
                    if self.first_request:
                        continue
                    run_handlers(self.new_message_event_handlers, [msg_object])
            else:
                continue
        if self.first_request:
            self.first_request = False

    def subscribe_on_new_message_event(self, handler: Callable):
        self.new_message_event_handlers.append(handler)

    def subscribe_on_new_order_event(self, handler: Callable):
        self.new_order_event_handlers.append(handler)


def run_handlers(handler_list: list[Callable], args: list):
    for func in handler_list:
        func(*args)
