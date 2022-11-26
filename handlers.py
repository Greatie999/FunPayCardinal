from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cardinal import Cardinal

from FunPayAPI.runner import MessageEvent, OrderEvent
from FunPayAPI.orders import Order
import FunPayAPI.users

from Utils import cardinal_tools

import time
import logging
import traceback
from threading import Thread


logger = logging.getLogger("Cardinal.handlers")


def log_msg_handler(msg: MessageEvent, *args):
    """
    Логирует полученное сообщение. Хэндлер.

    :param msg: сообщение.
    :return:
    """
    logger.info(f"Новое сообщение в переписке с пользователем $YELLOW{msg.sender_username}"
                f" (node: {msg.node_id}):")
    for line in msg.message_text.split("\n"):
        logger.info(line)


def send_response(msg: MessageEvent, cardinal: Cardinal, *args) -> bool:
    """
    Проверяет, является ли сообщение командой, если да - пытается отправить сообщение в ответ.

    :param msg: сообщение.
    :param cardinal: экземпляр Кардинала.
    :return: True - если сообщение отправлено, False - если нет.
    """
    response_text = cardinal_tools.format_msg_text(cardinal.auto_response_config[msg.message_text.strip()]["response"],
                                                   msg)
    new_msg_object = MessageEvent(msg.node_id, response_text, msg.sender_username, msg.send_time, msg.tag)

    response = cardinal.account.send_message(msg.node_id, response_text)
    if response.get("response") and response.get("response").get("error") is None:
        cardinal.runner.last_messages[msg.node_id] = new_msg_object
        logger.info(f"Отправил ответ пользователю {msg.sender_username}.")
        return True
    else:
        logger.warning(f"Произошла ошибка при отправке сообщения пользователю {msg.sender_username}.")
        logger.debug(f"{response}")
        return False


def send_response_handler(msg: MessageEvent, cardinal: Cardinal, *args):
    """
    Обертка, обрабатывающая ошибки cardinal.send_response(). Хэндлер.

    :param msg: сообщение.
    :param cardinal: экземпляр Кардинала.
    :return:
    """
    if not int(cardinal.main_config["FunPay"]["AutoResponse"]):
        return
    if msg.message_text.strip().lower() not in cardinal.auto_response_config:
        return

    logger.info(f"Получена команда \"{msg.message_text.strip()}\" "
                f"в переписке с пользователем $YELLOW{msg.sender_username} (node: {msg.node_id}).")
    done = False
    attempts = 3
    while not done and attempts:
        try:
            result = send_response(msg, cardinal, *args)
        except:
            logger.error(f"Произошла непредвиденная ошибка при отправке сообщения пользователю {msg.sender_username}.",)
            logger.debug(traceback.format_exc())
            logger.info("Следующая попытка через секунду.")
            attempts -= 1
            time.sleep(1)
            continue
        if not result:
            attempts -= 1
            logger.info("Следующая попытка через секунду.")
            time.sleep(1)
            continue
        done = True
    if not done:
        logger.error("Не удалось отправить ответ пользователю: превышено кол-во попыток.")
        return


def send_command_notification_handler(msg: MessageEvent, cardinal: Cardinal, *args):
    """
    Отправляет уведомление о введенной комманде в телеграм. Хэндлер.

    :param msg: сообщение с FunPay.
    :param cardinal: экземпляр Кардинала.
    :return:
    """
    if cardinal.telegram is None or msg.message_text.strip() not in cardinal.auto_response_config:
        return

    if cardinal.auto_response_config[msg.message_text].get("telegramNotification") is not None:
        if not int(cardinal.auto_response_config[msg.message_text]["telegramNotification"]):
            return

        if cardinal.auto_response_config[msg.message_text].get("notificationText") is None:
            text = f"Пользователь {msg.sender_username} ввел команду \"{msg.message_text}\"."
        else:
            text = cardinal_tools.format_msg_text(cardinal.auto_response_config[msg.message_text]["notificationText"],
                                                  msg)

        Thread(target=cardinal.telegram.send_notification, args=(text, )).start()


def notify_categories_raised_handler(game_id: int, category_names: list[str], wait_time: int,
                                     cardinal: Cardinal, *args) -> None:
    """
    Отправляет уведомление о поднятии лотов в Telegram.

    :param game_id: ID игры, к которой относятся категории.
    :param category_names: Названия поднятых категорий.
    :param wait_time: Предполагаемое время ожидания следующего поднятия.
    :param cardinal: экземпляр Кардинала.
    :return:
    """
    if cardinal.telegram is None or not int(cardinal.main_config["Telegram"]["lotsRaiseNotification"]):
        return

    cats_text = "".join(f"\"{i}\", " for i in category_names).strip()[:-1]
    Thread(target=cardinal.telegram.send_notification,
           args=(f"Поднял категории: {cats_text}. (ID игры: {game_id}\n"
                 f"Попробую еще раз через {cardinal_tools.time_to_str(wait_time)}.", )).start()


def send_product_text(node_id: int, text: str, order_id: str, cardinal: Cardinal, *args):
    """
    Отправляет сообщение с товаром в чат node_id.
    :param node_id: ID чата.
    :param text: текст сообщения.
    :param order_id: ID ордера.
    :param cardinal: экземпляр Кардинала.
    :return: результат отправки.
    """
    attempts = 3
    while attempts:
        try:
            cardinal.account.send_message(node_id, text)
            return True
        except:
            logger.error(f"Произошла ошибка при отправке товара для ордера {order_id}.")
            logger.debug(traceback.format_exc())
            logger.info("Следующая попытка через секунду.")
            attempts -= 1
            time.sleep(1)
    return False


def deliver_product(order: Order, cardinal: Cardinal, *args) -> list[bool | str] | None:
    """
    Форматирует текст товара и отправляет его покупателю.

    :param order: объект заказа.
    :param cardinal: экземпляр Кардинала.
    :return: результат выполнения. None - если лота нет в конфиге.
    [Результат выполнения, текст товара] - в любом другом случае.
    """
    # Ищем название лота в конфиге.
    delivery_obj = None
    for lot_name in cardinal.auto_delivery_config:
        if lot_name in order.title:
            delivery_obj = cardinal.auto_delivery_config[lot_name]
            break
    if delivery_obj is None:
        return None

    node_id = cardinal.account.get_node_id_by_username(order.buyer_name)
    response_text = cardinal_tools.format_order_text(delivery_obj["response"], order)

    # Проверяем, есть ли у лота файл с товарами. Если нет, то просто отправляем response лота.
    if delivery_obj.get("productsFilePath") is None:
        result = send_product_text(node_id, response_text, order.title, cardinal)
        return [result, response_text]

    # Получаем товар.
    product = cardinal_tools.get_product_from_json(delivery_obj.get("productsFilePath"))
    product_text = product[0]
    response_text = response_text.replace("$product", product_text)

    # Отправляем товар.
    result = send_product_text(node_id, response_text, order.id, cardinal)

    # Если произошла какая-либо ошибка при отправлении товара, возвращаем товар обратно в файл с товарами.
    if not result:
        cardinal_tools.add_product_to_json(delivery_obj.get("productsFilePath"), product_text)
    return [result, response_text]


def process_orders_handler(event: OrderEvent, cardinal: Cardinal, *args):
    """
    Обновляет список ордеров и запускает хэндлеры, если есть новые заказы.
    :param event: экземпляр эвента.
    :param cardinal: экземпляр Кардинала.
    :return:
    """
    if not int(cardinal.main_config["FunPay"]["AutoDelivery"]):
        return

    # Обновляем список ордеров.
    attempts = 3
    new_orders = {}
    while attempts:
        try:
            new_orders = cardinal.account.get_account_orders(include_completed=True,
                                                             exclude=list(cardinal.processed_orders.keys()))
            logger.info("Обновил список ордеров.")
            break
        except:
            logger.error("Не удалось обновить список ордеров.")
            logger.debug(traceback.format_exc())
            attempts -= 1
            time.sleep(1)
    if not attempts:
        logger.error("Не удалось обновить список ордеров: превышено кол-во попыток.")
        return

    # Обрабатываем каждый ордер по отдельности.
    for order_id in new_orders:
        cardinal.processed_orders[order_id] = new_orders[order_id]
        send_new_order_notification_handler(new_orders[order_id], cardinal)
        try:
            result = deliver_product(new_orders[order_id], cardinal)
            if result is None:
                logger.info(f"Лот \"{new_orders[order_id].title}\" не обнаружен в конфиге авто-выдачи.")
            elif not result[0]:
                logger.error(f"Ошибка при выдаче товара для ордера {order_id}: превышено кол-во попыток.")
                send_delivery_notification_handler(new_orders[order_id], "Превышено кол-во попыток.", cardinal,
                                                   errored=True)
            else:
                logger.info(f"Товар для ордера {order_id} выдан.")
                send_delivery_notification_handler(new_orders[order_id], result[1], cardinal)
        except Exception as e:
            logger.error(f"Произошла непредвиденная ошибка при обработке заказа {order_id}.")
            logger.debug(traceback.format_exc())
            send_delivery_notification_handler(new_orders[order_id], str(e), cardinal, errored=True)


def send_new_order_notification_handler(order: Order, cardinal: Cardinal, *args):
    if cardinal.telegram is None:
        return
    if not int(cardinal.main_config["Telegram"]["newOrderNotification"]):
        return

    text = f"""Новый ордер!
Покупатель: {order.buyer_name}.
ID ордера: {order.id}.
Сумма: {order.price}.
Лот: \"{order.title}\"."""
    Thread(target=cardinal.telegram.send_notification, args=(text, )).start()


def send_delivery_notification_handler(order: Order, delivery_text: str, cardinal: Cardinal,
                                       errored: bool = False, *args):
    if cardinal.telegram is None:
        return
    if not int(cardinal.main_config["Telegram"]["productsDeliveryNotification"]):
        return

    if errored:
        text = f"""Произошла ошибка при выдаче товара для ордера {order.id}.
Ошибка: {delivery_text}"""
    else:
        text = f"""Успешно выдал товар для ордера {order.id}.
----- ТОВАР -----
{delivery_text}"""

    Thread(target=cardinal.telegram.send_notification, args=(text, )).start()


def updates_lots_state_handler(event: OrderEvent, cardinal: Cardinal, *args):
    if not int(cardinal.main_config["FunPay"]["autoRestore"]):
        return
    attempts = 3
    lots_info = []
    while attempts:
        try:
            lots_info = FunPayAPI.users.get_user_lots_info(cardinal.account.id)["lots"]
            break
        except:
            logger.error("Произошла пошибка при получении информации о лотах.")
            logger.debug(traceback.format_exc())
            attempts -= 1
    if not attempts:
        logger.error("Не удалось получить информацию о лотах: превышено кол-во попыток.")
        return

    lots_ids = [i.offer_id for i in lots_info]
    for lot in cardinal.lots:
        if lot.offer_id not in lots_ids:
            try:
                cardinal.account.change_lot_state(lot.offer_id, lot.game_id)
                logger.info(f"Активировал лот {lot.offer_id}.")
            except:
                logger.error(f"Не удалось активировать лот {lot.offer_id}.")
                logger.debug(traceback.format_exc())


REGISTER_TO_MESSAGE_EVENT = [log_msg_handler,
                             send_response_handler,
                             send_command_notification_handler
]

REGISTER_TO_RAISE_EVENT = [
    notify_categories_raised_handler
]

REGISTER_TO_ORDER_EVENT = [
    process_orders_handler,
    updates_lots_state_handler
]