import sys
import os.path
import time
import configparser
import traceback
import logging
from typing import Callable, Generator
import importlib.util

from threading import Thread

import FunPayAPI.users
import FunPayAPI.account
import FunPayAPI.categories
import FunPayAPI.orders
import FunPayAPI.runner
import FunPayAPI.lots
import FunPayAPI.enums

from Utils import cardinal_tools
import handlers

import telegram


logger = logging.getLogger("Cardinal")


class Cardinal:
    def __init__(self,
                 main_config: configparser.ConfigParser,
                 # lots_config: configparser.ConfigParser,
                 auto_response_config: configparser.ConfigParser,
                 auto_delivery_config: configparser.ConfigParser
                 ):

        # Конфиги
        self.main_config = main_config
        # self.lots_config = lots_config
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
        # После инициализации Кардинала.
        # Аргументы для хэндлеров: экземпляр Кардинала (self)
        self.bot_init_handlers: list[Callable[[Cardinal, any], any]] = []

        # После запуска Кардинала.
        # Аргументы для хэндлеров: экземпляр Кардинала (self)
        self.bot_start_handlers: list[Callable[[Cardinal, any], any]] = []

        # После остановки Кардинала.
        # Аргументы для хэндлеров: экземпляр Кардинала (self)
        self.bot_stop_handlers: list[Callable[[Cardinal, any], any]] = []

        # После обнаружения нового сообщения в чате.
        # Аргументы для хэндлеров: экземпляр MessageEvent, экземпляр Кардинала (self)
        self.message_event_handlers: list[Callable[[FunPayAPI.runner.MessageEvent, Cardinal, any], any]] = []

        # После уведомления от FunPay о том, что есть изменения в ордерах.
        # Аргументы для хэндлеров: экземпляр OrderEvent, экземпляр Кардинала (self)
        self.orders_updates_event_handlers: list[Callable[[FunPayAPI.runner.OrderEvent, Cardinal, any], any]] = []

        # После обнаружения нового ордера.
        # Аргументы для хэндлеров: экземпляр Order, экземпляр Кардинала (self)
        self.new_order_event_handlers: list[Callable[[FunPayAPI.orders.Order, Cardinal, any], any]] = []

        # После отправки продукта (независимо от результата).
        # Аргументы для хэндлеров: экземпляр Order, текст товара / ошибки: str, экземпляр Кардинала (self),
        # результат доставки (True/False)
        self.delivery_event_handlers: list[Callable] = []

        # После поднятия лотов (успешного поднятия).
        # Аргументы для хэндлеров: game_id категории: int, список названий категорий: list[str],
        # экземпляр Кардинала (self)
        self.raise_lots_handlers: list[Callable] = []

        self.register_var_names = {
            "REGISTER_TO_INIT_EVENT": self.bot_init_handlers,
            "REGISTER_TO_START_EVENT": self.bot_start_handlers,
            "REGISTER_TO_STOP_EVENT": self.bot_stop_handlers,
            "REGISTER_TO_NEW_MESSAGE_EVENT": self.message_event_handlers,
            "REGISTER_TO_RAISE_EVENT": self.raise_lots_handlers,
            "REGISTER_TO_ORDERS_UPDATE_EVENT": self.orders_updates_event_handlers,
            "REGISTER_TO_NEW_ORDER_EVENT": self.new_order_event_handlers,
            "REGISTER_TO_DELIVERY_EVENT": self.delivery_event_handlers
        }

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
                logger.info(f"$MAGENTAПолучил информацию о лотах аккаунта. Всего категорий: $YELLOW{len(categories)}.")
                logger.info(f"$MAGENTAВсего лотов: $YELLOW{len(lots)}")
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
                orders = self.account.get_account_orders(include_completed=True)
                orders_dict = {}
                for order in orders:
                    orders_dict[order.id] = order
                self.processed_orders = orders_dict
                logger.info(f"$MAGENTAПолучил информацию об ордерах аккаунта.")
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
        Загружает плагины и добавляет хэндлеры в self.message_event_handlers и self.new_order_event_handlers
        """
        self.runner = FunPayAPI.runner.Runner(self.account)
        logger.info("$MAGENTARunner инициализирован.")

    def __init_telegram(self) -> None:
        """
        Инициализирует Telegram бота.
        :return:
        """
        self.telegram = telegram.TGBot(self.main_config)
        self.telegram.init()

    def __add_handlers(self, obj) -> None:
        """
        Добавляет хэндлеры из переданного объекта.

        :param obj: модуль (плагин)
        """
        for name in self.register_var_names:
            try:
                functions = getattr(obj, name)
            except AttributeError:
                continue
            for handler in functions:
                self.register_var_names[name].append(handler)

        logger.info(f"Хэндлеры из $YELLOW{obj.__name__}.py$color зарегистрированы.")

    def __load_plugins(self) -> None:
        """
        Загружает плагины из папки plugins.
        """
        if not os.path.exists("plugins"):
            logger.warning("Папка с плагинами не обнаружена.")
            return
        plugins = [file for file in os.listdir("plugins") if file.endswith(".py")]
        if not len(plugins):
            logger.info("Плагины не обнаружены.")
            return
            
        sys.path.append("plugins")
        for file in plugins:
            try:
                spec = importlib.util.spec_from_file_location(f"plugins.{file[:-3]}", f"plugins/{file}")
                plugin = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(plugin)
                logger.info(f"Плагин $YELLOW{file}$color загружен.")
            except:
                logger.error(f"Не удалось загрузить плагин {file}. Подробнее в файле логов.")
                logger.debug(traceback.format_exc())
                continue
            self.__add_handlers(plugin)

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
                self.run_handlers(self.raise_lots_handlers, (cat.game_id, response["raised_category_names"],
                                                             response["wait"], self, ))
        return min_next_time

    def send_message(self, msg: FunPayAPI.runner.MessageEvent):
        """
        Отправляет сообщение в чат c ID node_id. Если сообщение доставлено - добавляет его в список последних сообщений
        в runner.

        :param msg: объект MessageEvent.
        :return:
        """
        if self.main_config["Other"]["botName"] != "-":
            msg.message_text = f"{self.main_config['Other']['botName']}\n" + msg.message_text

        response = self.account.send_message(msg.node_id, msg.message_text)
        if response.get("response") and response.get("response").get("error") is None:
            if len(msg.message_text) > 250:
                obj_text = msg.message_text[:250]
            else:
                obj_text = msg.message_text

            if self.runner is not None:
                new_msg_obj = FunPayAPI.runner.MessageEvent(msg.node_id,
                                                            obj_text,
                                                            msg.sender_username,
                                                            msg.send_time,
                                                            msg.tag)

                self.runner.last_messages[msg.node_id] = new_msg_obj
            logger.info(f"Отправил сообщение в чат $YELLOW{msg.node_id}.")
            return True
        else:
            logger.warning(f"Произошла ошибка при отправке сообщения в чат $YELLOW{msg.node_id}.")
            logger.debug(f"{response}")
            return False

    # Бесконечные циклы.
    def lots_raise_loop(self):
        """
        Запускает бесконечный цикл поднятия категорий (если autoRaise в _main.cfg == 1)

        :return:
        """
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
        logger.info("$CYANRunner запущен.")
        if int(self.main_config["FunPay"]["infiniteOnline"]):
            logger.info("$CYANВечный онлайн запущен.")

        if int(self.main_config["FunPay"]["autoResponse"]):
            logger.info(f"$CYANАвто-ответ запущен. "
                        f"Загружено $YELLOW{len(self.auto_response_config.sections())} $CYANкоманд.")

        if int(self.main_config["FunPay"]["autoDelivery"]):
            logger.info(f"$CYANАвто-выдача товара запущена. "
                        f"Загружено $YELLOW{len(self.auto_delivery_config.sections())} $CYANлотов для выдачи.")

        if int(self.main_config["FunPay"]["autoRestore"]):
            logger.info(f"$CYANАвто-восстановление лота запущено. "
                        f"Загружено $YELLOW{len(self.lots)} $CYANлотов.")
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
                    self.run_handlers(self.message_event_handlers, (event, self, ))

                elif event.type == FunPayAPI.enums.EventTypes.NEW_ORDER:
                    self.process_orders(event)

    def process_orders(self, event: FunPayAPI.runner.OrderEvent):
        """
        Обновляет список ордеров и запускает хэндлеры, если есть новые заказы.

        :return:
        """
        # Обновляем список ордеров.
        self.run_handlers(self.orders_updates_event_handlers, (event, self, ))
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
        for order in new_orders:
            self.processed_orders[order.id] = order
            self.run_handlers(self.new_order_event_handlers, (order, self, ))

    # Функции запуска / остановки Кардинала.
    def init(self):
        """
        Инициализирует все необходимые для работы Кардинала классы.

        :return:
        """
        self.__init_account()
        self.__add_handlers(handlers)
        self.__load_plugins()

        if any([
            int(self.main_config["FunPay"]["autoRaise"]),
            int(self.main_config["FunPay"]["autoRestore"])
        ]):
            self.__init_user_lots_info()

        if any([
            int(self.main_config["FunPay"]["autoDelivery"]),
            int(self.main_config["FunPay"]["autoRestore"])
        ]):
            self.__init_orders()

        if any([
            int(self.main_config["FunPay"]["autoDelivery"]),
            int(self.main_config["FunPay"]["autoResponse"]),
            int(self.main_config["FunPay"]["autoRestore"]),
            int(self.main_config["FunPay"]["infiniteOnline"])
        ]):
            self.__init_runner()

        if int(self.main_config["Telegram"]["enabled"]):
            self.__init_telegram()
            self.telegram.cardinal = self

        self.run_handlers(self.bot_init_handlers, (self, ))

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

        self.run_handlers(self.bot_start_handlers, (self, ))

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
