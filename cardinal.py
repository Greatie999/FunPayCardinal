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
import handlers

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
        self.message_event_handlers: list[Callable[[FunPayAPI.runner.MessageEvent, Cardinal, any], any]] = []
        self.orders_event_handlers: list[Callable[[FunPayAPI.runner.OrderEvent, Cardinal, any], any]] = []
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

    def __init_telegram(self) -> None:
        """
        Инициализирует Telegram бота.
        :return:
        """
        self.telegram = telegram.TGBot(self.main_config)
        self.telegram.init()

    def __init_handlers(self) -> None:
        var_names = {
            "REGISTER_TO_INIT_EVENT": self.bot_init_handlers,
            "REGISTER_TO_START_EVENT": self.bot_start_handlers,
            "REGISTER_TO_STOP_EVENT": self.bot_stop_handlers,
            "REGISTER_TO_MESSAGE_EVENT": self.message_event_handlers,
            "REGISTER_TO_RAISE_EVENT": self.raise_lots_handlers,
            "REGISTER_TO_ORDER_EVENT": self.orders_event_handlers,
        }

        for name in var_names:
            try:
                functions = getattr(handlers, name)
            except AttributeError:
                continue
            for handler in functions:
                var_names[name].append(handler)

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
                                                             response["wait"], self, ])
        return min_next_time

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
                    self.run_handlers(self.message_event_handlers, [event, self, ])

                elif event.type == FunPayAPI.enums.EventTypes.NEW_ORDER:
                    self.run_handlers(self.orders_event_handlers, [event, self, ])

    # Функции запуска / остановки Кардинала.
    def init(self):
        """
        Инициализирует все необходимые для работы Кардинала классы.
        :return:
        """
        self.__init_account()
        self.__init_handlers()

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
