import time
import configparser
import traceback
import logging
from typing import Callable, Generator

from threading import Thread

import FunPayAPI.users
import FunPayAPI.account
import FunPayAPI.categories
import FunPayAPI.orders
import FunPayAPI.runner
import FunPayAPI.lots
import FunPayAPI.enums

from Utils import cardinal_tools

import telegram


logger = logging.getLogger("Cardinal")


class Cardinal:
    def __init__(self,
                 main_config: configparser.ConfigParser,
                 lots_config: configparser.ConfigParser,
                 auto_response_config: configparser.ConfigParser,
                 auto_delivery_config: configparser.ConfigParser
                 ):

        # Конфиги
        self.main_config = main_config
        self.lots_config = lots_config
        self.auto_response_config = auto_response_config
        self.auto_delivery_config = auto_delivery_config

        # Прочее
        self.running = False
        self.account: FunPayAPI.account.Account | None = None
        self.runner: FunPayAPI.runner.Runner | None = None
        self.telegram: telegram.TGBot | None = None

        # Категории
        self.categories: list[FunPayAPI.categories.Category] | None = None
        # ID игр категорий. Нужно для проверки возможности поднять ту или иную категорию.
        # Формат хранения: {ID игры: следующее время поднятия}
        self.game_ids = {}
        self.lots: list[FunPayAPI.lots.Lot] | None = None
        # Обработанные ордеры
        # {"id ордера": ордер}
        self.processed_orders: dict[str, FunPayAPI.orders.Order] | None = None

        # Хэндлеры
        self.bot_init_handlers: list[Callable] = []
        self.bot_start_handlers: list[Callable] = []
        self.bot_stop_handlers: list[Callable] = []
        self.message_event_handlers: list[Callable[[FunPayAPI.runner.MessageEvent], any]] = []
        self.orders_event_handlers: list[Callable[[FunPayAPI.runner.OrderEvent], any]] = []
        self.raise_lots_handlers: list[Callable] = []

    # Инициирование
    def __init_account(self) -> None:
        """
        Инициализирует класс аккаунта (self.account)
        """
        while True:
            try:
                self.account = FunPayAPI.account.get_account(self.main_config["FunPay"]["golden_key"])
                greeting_text = cardinal_tools.create_greetings(self.account)
                for line in greeting_text.split("\n"):
                    logger.info(line)
                break
            except TimeoutError:
                logger.warning("Не удалось загрузить данные об аккаунте: превышен тайм-аут ожидания.")
                logger.warning("Повторю попытку через 2 секунды...")
                time.sleep(2)
            except:
                logger.error("Не удалось загрузить данные об аккаунте: неизвестная ошибка.")
                logger.debug(traceback.format_exc())
                logger.warning("Повторю попытку через 2 секунды...")
                time.sleep(2)
            # todo: добавить обработку других исключений

    def __init_user_lots_info(self) -> None:
        """
        Загружает данные о лотах категориях аккаунта + восстанавливает game_id каждой категории из кэша, либо
        отправляет дополнительные запросы к FunPay. (self.categories)

        :return: None
        """
        # Получаем категории аккаунта.
        while True:
            try:
                user_lots_info = FunPayAPI.users.get_user_lots_info(self.account.id)
                categories = user_lots_info["categories"]
                lots = user_lots_info["lots"]
                logger.info(f"$CYANПолучил информацию о лотах аккаунта. Всего категорий: $YELLOW{len(categories)}.")
                logger.info(f"$CYANВсего лотов: $YELLOW{len(lots)}")
                break
            except TimeoutError:
                logger.warning("Не удалось загрузить данные о категориях аккаунта: превышен тайм-аут ожидания.")
                logger.warning("Повторю попытку через 2 секунды...")
                time.sleep(2)
            except:
                logger.error("Не удалось загрузить данные о категориях аккаунта: неизвестная ошибка.")
                logger.debug(traceback.format_exc())
                logger.warning("Повторю попытку через 2 секунды...")
                time.sleep(2)
            # todo: добавить обработку других исключений

        # Привязываем к каждой категории её game_id. Если категория кэширована - берем game_id из кэша,
        # если нет - делаем запрос к FunPay.
        # Присваиваем каждому лоту game_id
        # Так же добавляем game_id категории в self.game_ids
        logger.info("Получаю ID игр, к которым относятся лоты и категории...")
        cached_categories = cardinal_tools.load_cached_categories()
        for index, cat in enumerate(categories):
            cached_category_name = f"{cat.id}_{cat.type.value}"
            if cached_category_name in cached_categories:
                categories[index].game_id = cached_categories[cached_category_name]
                # Присваиваем game_id каждому лоту это категории.
                category_lots = [(ind, lot) for ind, lot in enumerate(lots) if lot.category_id == cat.id]
                for lot_tuple in category_lots:
                    lots[lot_tuple[0]].game_id = cat.game_id
                logger.info(f"Доп. данные о категории \"{cat.title}\" найдены в кэше.")
                continue

            logger.warning(f"Доп. данные о категории \"{cat.title}\" не найдены в кэше.")
            logger.info("Отправляю запрос к FunPay...")
            while True:
                try:
                    game_id = self.account.get_category_game_id(cat)
                    categories[index].game_id = game_id
                    # Присваиваем game_id каждому лоту этой категории.
                    category_lots = [(ind, lot) for ind, lot in enumerate(lots) if lot.category_id == cat.id]
                    for lot_tuple in category_lots:
                        lots[lot_tuple[0]].game_id = game_id
                    logger.info(f"Доп. данные о категории \"{cat.title}\" получены!")
                    break
                except TimeoutError:
                    logger.warning(f"Не удалось получить ID игры, к которой относится категория \"{cat.title}\": "
                                   f"превышен тайм-аут ожидания.")
                    logger.warning("Повторю попытку через 2 секунды...")
                    time.sleep(2)
                except:
                    logger.error(f"Не удалось получить ID игры, к которой относится категория \"{cat.title}\": "
                                 f"неизвестная ошибка.")
                    logger.debug(traceback.format_exc())
                    logger.warning("Повторю попытку через 2 секунды...")
                    time.sleep(2)

        self.categories = categories
        self.lots = lots
        logger.info("Кэширую данные о категориях...")
        cardinal_tools.cache_categories(self.categories)

    def __init_orders(self) -> None:
        """
        Загружает данные об ордерах пользователя.
        :return:
        """
        while True:
            try:
                self.processed_orders = self.account.get_account_orders(include_completed=True)
                logger.info(f"$CYANПолучил информацию об ордерах аккаунта.")
                break
            except TimeoutError:
                logger.warning("Не удалось получить информацию об ордерах аккаунта: превышен тайм-аут ожидания.")
                logger.warning("Повторю попытку через 2 секунды...")
                time.sleep(2)
            except:
                logger.error("Не удалось получить информацию об ордерах аккаунта: превышен тайм-аут ожидания.")
                logger.debug(traceback.format_exc())
                logger.warning("Повторю попытку через 2 секунды...")
                time.sleep(2)

    def __init_runner(self) -> None:
        """
        Инициализирует класс раннер'а (self.runner),
        Загружает плагины и добавляет хэндлеры в self.message_event_handlers и self.orders_event_handlers
        """
        self.runner = FunPayAPI.runner.Runner(self.account)
        self.message_event_handlers.append(self.log_msg_handler)
        self.message_event_handlers.append(self.send_response_handler)
        self.message_event_handlers.append(self.send_command_notification_handler)

        self.orders_event_handlers.append(self.process_orders_handler)
        self.orders_event_handlers.append(self.updates_lots_state_handler)

    def __init_telegram(self) -> None:
        """
        Инициализирует Telegram бота.
        :return:
        """
        self.telegram = telegram.TGBot(self.main_config)
        self.telegram.init()

    # Основные функции
    def raise_lots(self) -> int:
        """
        Пытается поднять лоты.
        :return: предположительное время, когда нужно снова запустить данную функцию.
        """
        # Минимальное время до следующего вызова данной функции.
        min_next_time = -1
        for cat in self.categories:
            # Если game_id данной категории уже находится в self.game_ids, но время поднятия категорий
            # данной игры еще не настало - пропускам эту категорию.
            if cat.game_id in self.game_ids and self.game_ids[cat.game_id] > int(time.time()):
                if min_next_time == -1 or self.game_ids[cat.game_id] < min_next_time:
                    min_next_time = self.game_ids[cat.game_id]
                continue

            # В любом другом случае пытаемся поднять лоты всех категорий, относящихся к игре cat.game_id
            try:
                response = self.account.raise_game_categories(cat)
                logger.debug(str(response))
            except:
                logger.error(f"Не удалось поднять категорию \"{cat.title}\": неизвестная ошибка.")
                logger.debug(traceback.format_exc())
                next_time = int(time.time()) + 10
                if min_next_time == -1 or next_time < min_next_time:
                    min_next_time = next_time
                continue
                # todo: добавить обработку исключений.
            if not response["complete"]:
                logger.warning(f"Не удалось поднять категорию \"{cat.title}\". "
                               f"Попробую еще раз через {cardinal_tools.time_to_str(response['wait'])}.")
                logger.debug(response["response"])
                next_time = int(time.time()) + response["wait"]
                self.game_ids[cat.game_id] = next_time
                if min_next_time == -1 or next_time < min_next_time:
                    min_next_time = next_time
            else:
                for category_name in response["raised_category_names"]:
                    logger.info(f"Поднял категорию \"{category_name}\". ")
                logger.info(f"Все категории, относящиеся к игре с ID {cat.game_id} подняты!")
                logger.info(f"Попробую еще раз через  {cardinal_tools.time_to_str(response['wait'])}.")
                next_time = int(time.time()) + response['wait']
                self.game_ids[cat.game_id] = next_time
                if min_next_time == -1 or next_time < min_next_time:
                    min_next_time = next_time
                self.run_handlers(self.raise_lots_handlers, [cat.game_id, response["raised_category_names"],
                                                             response["wait"]])
        return min_next_time

    # Бесконечные циклы.
    def lots_raise_loop(self):
        """
        Запускает бесконечный цикл поднятия категорий (если autoRaise в _main.cfg == 1)
        :return:
        """
        self.raise_lots_handlers.append(self.notify_categories_raised_handler)
        logger.info("$CYANАвто-поднятие лотов запущено.")
        while True and self.running:
            try:
                next_time = self.raise_lots()
            except:
                logger.error("Не удалось поднять лоты: произошла неизвестная ошибка.")
                logger.debug(traceback.format_exc())
                logger.info("Попробую через 10 секунд.")
                time.sleep(10)
                continue
            delay = next_time - int(time.time())
            if delay < 0:
                delay = 0
            time.sleep(delay)

    def listen_runner(self) -> Generator[list[FunPayAPI.runner.MessageEvent | FunPayAPI.runner.OrderEvent], None, None]:
        """
        Запускает бесконечный цикл получения эвентов от FunPay.
        """
        if not any(
                [
                    int(self.main_config["FunPay"]["autoResponse"]),
                    int(self.main_config["FunPay"]["autoDelivery"])
                ]
        ):
            return None
        logger.info("$CYANRunner запущен.")
        while self.running:
            try:
                events = self.runner.get_updates()
                yield events
            except:
                logger.error("Не удалось получить список эвентов.")
                logger.debug(traceback.format_exc())
                yield []
            time.sleep(6)

    def process_funpay_events(self):
        """
        "Слушает" self.listen_runner(), запускает хэндлеры, привязанные к эвенту.
        :return:
        """
        for events in self.listen_runner():
            for event in events:
                if event.type == FunPayAPI.enums.EventTypes.NEW_MESSAGE:
                    self.run_handlers(self.message_event_handlers, [event, ])

                elif event.type == FunPayAPI.enums.EventTypes.NEW_ORDER:
                    self.run_handlers(self.orders_event_handlers, [event, ])

    # Встроенные хэндлеры
    def send_response(self, msg: FunPayAPI.runner.MessageEvent) -> bool:
        """
        Проверяет, является ли сообщение командой, если да - пытается отправить сообщение в ответ.
        :param msg: сообщение.
        :return: True - если сообщение отправлено, False - если нет.
        """
        response_text = cardinal_tools.format_msg_text(self.auto_response_config[msg.message_text.strip()]["response"],
                                                       msg)
        new_msg_object = FunPayAPI.runner.MessageEvent(msg.node_id,
                                                       response_text,
                                                       msg.sender_username,
                                                       msg.send_time,
                                                       msg.tag)

        response = self.account.send_message(msg.node_id, response_text)
        if response.get("response") and response.get("response").get("error") is None:
            self.runner.last_messages[msg.node_id] = new_msg_object
            logger.info(f"Отправил ответ пользователю {msg.sender_username}.")
            return True
        else:
            logger.warning(f"Произошла ошибка при отправке сообщения пользователю {msg.sender_username}.")
            logger.debug(f"{response}")
            return False

    def send_response_handler(self, msg: FunPayAPI.runner.MessageEvent):
        """
        Оболочка, обрабатывающая ошибки self.send_response(). Хэндлер.
        :param msg: сообщение.
        :return:
        """
        if not int(self.main_config["FunPay"]["AutoResponse"]):
            return
        if msg.message_text.strip().lower() not in self.auto_response_config:
            return

        logger.info(f"Получена команда \"{msg.message_text.strip()}\" "
                    f"в переписке с пользователем $YELLOW{msg.sender_username} (node: {msg.node_id}).")
        done = False
        attempts = 3
        while not done and attempts:
            try:
                result = self.send_response(msg)
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

    def log_msg_handler(self, msg: FunPayAPI.runner.MessageEvent):
        """
        Логирует полученное сообщение. Хэндлер.
        :param msg: сообщение.
        :return:
        """
        logger.info(f"Новое сообщение в переписке с пользователем $YELLOW{msg.sender_username}"
                    f" (node: {msg.node_id}):")
        for line in msg.message_text.split("\n"):
            logger.info(line)

    def send_command_notification_handler(self, msg: FunPayAPI.runner.MessageEvent):
        """
        Отправляет уведомление о введенной комманде в телеграм. Хэндлер.
        :param msg: сообщение с FunPay.
        :return:
        """
        if self.telegram is None or msg.message_text.strip() not in self.auto_response_config:
            return

        if self.auto_response_config[msg.message_text].get("telegramNotification") is not None:
            if not int(self.auto_response_config[msg.message_text]["telegramNotification"]):
                return

            if self.auto_response_config[msg.message_text].get("notificationText") is None:
                text = f"Пользователь {msg.sender_username} ввел команду \"{msg.message_text}\"."
            else:
                text = cardinal_tools.format_msg_text(self.auto_response_config[msg.message_text]["notificationText"],
                                                      msg)

            Thread(target=self.telegram.send_notification, args=(text, )).start()

    def notify_categories_raised_handler(self, game_id: int, category_names: list[str], wait_time: int) -> None:
        """
        Отправляет уведомление о поднятии лотов в Telegram.
        :param game_id: ID игры, к которой относятся категории.
        :param category_names: Названия поднятых категорий.
        :param wait_time: Предполагаемое время ожидания следующего поднятия.
        :return:
        """
        if self.telegram is None or not int(self.main_config["Telegram"]["lotsRaiseNotification"]):
            return

        cats_text = "".join(f"\"{i}\", " for i in category_names).strip()[:-1]
        Thread(target=self.telegram.send_notification,
               args=(f"Поднял категории: {cats_text}. (ID игры: {game_id}\n"
                     f"Попробую еще раз через {cardinal_tools.time_to_str(wait_time)}.", )).start()

    def process_orders_handler(self, *args):
        """
        Обрабатывает ордер.
        :return:
        """
        if not int(self.main_config["FunPay"]["AutoDelivery"]):
            return

        # Обновляем список ордеров.
        attempts = 3
        new_orders = {}
        while attempts:
            try:
                new_orders = self.account.get_account_orders(include_completed=True,
                                                             exclude=list(self.processed_orders.keys()))
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
            self.processed_orders[order_id] = new_orders[order_id]
            self.send_new_order_notification_handler(new_orders[order_id])
            try:
                result = self.deliver_product(new_orders[order_id])
                if result is None:
                    logger.info(f"Лот \"{new_orders[order_id].title}\" не обнаружен в конфиге авто-выдачи.")
                elif not result[0]:
                    logger.error(f"Ошибка при выдаче товара для ордера {order_id}: превышено кол-во попыток.")
                    self.send_delivery_notification_handler(new_orders[order_id], "Превышено кол-во попыток.",
                                                            errored=True)
                else:
                    logger.info(f"Товар для ордера {order_id} выдан.")
                    self.send_delivery_notification_handler(new_orders[order_id], result[1])
            except Exception as e:
                logger.error(f"Произошла непредвиденная ошибка при обработке заказа {order_id}.")
                logger.debug(traceback.format_exc())
                self.send_delivery_notification_handler(new_orders[order_id], str(e), errored=True)

    def deliver_product(self, order: FunPayAPI.orders.Order) -> list[bool | str] | None:
        """
        Форматирует текст товара и отправляет его покупателю.
        :param order: объект заказа.
        :return: результат выполнения. None - если лота нет в конфиге.
        [Результат выполнения, текст товара] - в любом другом случае.
        """
        # Ищем название лота в конфиге.
        delivery_obj = None
        for lot_name in self.auto_delivery_config:
            if lot_name in order.title:
                delivery_obj = self.auto_delivery_config[lot_name]
                break
        if delivery_obj is None:
            return None

        node_id = self.account.get_node_id_by_username(order.buyer_name)
        response_text = cardinal_tools.format_order_text(delivery_obj["response"], order)

        # Проверяем, есть ли у лота файл с товарами. Если нет, то просто отправляем response лота.
        if delivery_obj.get("productsFilePath") is None:
            result = self.send_product_text(node_id, response_text, order.title)
            return [result, response_text]

        # Получаем товар.
        product = cardinal_tools.get_product_from_json(delivery_obj.get("productsFilePath"))
        product_text = product[0]
        response_text = response_text.replace("$product", product_text)

        # Отправляем товар.
        result = self.send_product_text(node_id, response_text, order.id)

        # Если произошла какая-либо ошибка при отправлении товара, возвращаем товар обратно в файл с товарами.
        if not result:
            cardinal_tools.add_product_to_json(delivery_obj.get("productsFilePath"), product_text)
        return [result, response_text]

    def send_product_text(self, node_id: int, text: str, order_id: str):
        """
        Отправляет сообщение с товаром в чат node_id.
        :param node_id: ID чата.
        :param text: текст сообщения.
        :param order_id: ID ордера.
        :return: результат отправки.
        """
        attempts = 3
        while attempts:
            try:
                self.account.send_message(node_id, text)
                return True
            except:
                logger.error(f"Произошла ошибка при отправке товара для ордера {order_id}.")
                logger.debug(traceback.format_exc())
                logger.info("Следующая попытка через секунду.")
                attempts -= 1
                time.sleep(1)
        return False

    def send_new_order_notification_handler(self, order: FunPayAPI.orders.Order):
        if self.telegram is None:
            return
        if not int(self.main_config["Telegram"]["newOrderNotification"]):
            return

        text = f"""Новый ордер!
Покупатель: {order.buyer_name}.
ID ордера: {order.id}.
Сумма: {order.price}.
Лот: \"{order.title}\"."""
        Thread(target=self.telegram.send_notification, args=(text, )).start()

    def send_delivery_notification_handler(self, order: FunPayAPI.orders.Order, delivery_text: str,
                                           errored: bool = False):
        if self.telegram is None:
            return
        if not int(self.main_config["Telegram"]["productsDeliveryNotification"]):
            return

        if errored:
            text = f"""Произошла ошибка при выдаче товара для ордера {order.id}.
Ошибка: {delivery_text}"""
        else:
            text = f"""Успешно выдал товар для ордера {order.id}.
----- ТОВАР -----
{delivery_text}"""

        Thread(target=self.telegram.send_notification, args=(text, )).start()

    def updates_lots_state_handler(self, *args):
        if not int(self.main_config["FunPay"]["autoRestore"]):
            return
        attempts = 3
        lots_info = []
        while attempts:
            try:
                lots_info = FunPayAPI.users.get_user_lots_info(self.account.id)["lots"]
                break
            except:
                logger.error("Произошла пошибка при получении информации о лотах.")
                logger.debug(traceback.format_exc())
                attempts -= 1
        if not attempts:
            logger.error("Не удалось получить информацию о лотах: превышено кол-во попыток.")
            return

        lots_ids = [i.offer_id for i in lots_info]
        for lot in self.lots:
            if lot.offer_id not in lots_ids:
                try:
                    self.account.change_lot_state(lot.offer_id, lot.game_id)
                    logger.info(f"Активировал лот {lot.offer_id}.")
                except:
                    logger.error(f"Не удалось активировать лот {lot.offer_id}.")
                    logger.debug(traceback.format_exc())

    # Функции запуска / остановки Кардинала.
    def init(self):
        """
        Инициализирует все необходимые для работы Кардинала классы.
        :return:
        """
        self.__init_account()

        if int(self.main_config["FunPay"]["autoRaise"]):
            self.__init_user_lots_info()

        if any([
            int(self.main_config["FunPay"]["autoDelivery"]),
            int(self.main_config["FunPay"]["autoRestore"])
        ]):
            self.__init_orders()

        if any([
            int(self.main_config["FunPay"]["autoDelivery"]),
            int(self.main_config["FunPay"]["autoResponse"]),
            int(self.main_config["FunPay"]["infiniteOnline"])
        ]):
            self.__init_runner()

        if int(self.main_config["Telegram"]["enabled"]):
            self.__init_telegram()

    def run(self):
        """
        Запускает все потоки.
        :return:
        """
        self.running = True

        if self.categories and int(self.main_config["FunPay"]["autoRaise"]):
            Thread(target=self.lots_raise_loop).start()

        if self.runner:
            Thread(target=self.process_funpay_events).start()

        if self.telegram:
            Thread(target=self.telegram.run).start()
            self.telegram.send_notification("Бот запущен!")

    def stop(self):
        """
        Останавливает все потоки.
        :return:
        """
        self.running = False

    # Прочее
    def run_handlers(self, handlers: list[Callable], args) -> None:
        """
        Выполняет функции из списка handlers.
        :param handlers: Список функций.
        :param args: аргументы для функций.
        :return:
        """
        for func in handlers:
            try:
                func(*args)
            except:
                logger.error("Произошла ошибка при выполнении хэндлера.")
                logger.debug(traceback.format_exc())
