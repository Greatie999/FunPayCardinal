"""
В данном модуле написаны инструменты, которыми пользуется Telegram бот.
"""

import json
import os.path


def load_authorized_users() -> list[int]:
    """
    Загружает авторизированных пользователей из кэша.

    :return: список из id авторизированных пользователей.
    """
    if not os.path.exists("storage/cache/tg_authorized_users.json"):
        return []
    with open("storage/cache/tg_authorized_users.json", "r", encoding="utf-8") as f:
        data = f.read()
    return json.loads(data)


def load_chat_ids() -> list[int]:
    """
    Загружает список чатов для уведомлений из кэша.

    :return: список из id чатов для уведомлений.
    """
    if not os.path.exists("storage/cache/tg_chat_ids.json"):
        return []
    with open("storage/cache/tg_chat_ids.json", "r", encoding="utf-8") as f:
        data = f.read()
    return json.loads(data)


def save_authorized_users(users: list[int]) -> None:
    """
    Сохраняет id авторизированных пользователей в кэш.

    :param users: список id авторизированных пользователей.
    :return:
    """
    if not os.path.exists("storage/cache/"):
        os.makedirs("storage/cache/")

    with open("storage/cache/tg_authorized_users.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(users))


def save_chat_ids(chat_ids: list[int]) -> None:
    """
    Сохраняет id чатов для уведомлений в кэш.

    :param chat_ids: список id чатов для уведомлений.
    :return:
    """
    if not os.path.exists("storage/cache/"):
        os.makedirs("storage/cache/")

    with open("storage/cache/tg_chat_ids.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(chat_ids))
