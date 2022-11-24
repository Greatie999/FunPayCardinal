import time
import configparser
import traceback
import logging
from typing import Callable, Generator

from colorama import Fore
from threading import Thread

import FunPayAPI.users
import FunPayAPI.account
import FunPayAPI.categories
import FunPayAPI.orders
import FunPayAPI.runner
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

        # Обработанные офферы
        # {"id ордера": ордер}
        self.processed_orders: dict[str, FunPayAPI.orders.Order] = {}

        # Хэндлеры
        self.bot_init_handlers: list[Callable] = []
        self.bot_start_handlers: list[Callable] = []
        self.bot_stop_handlers: list[Callable] = []
        self.message_event_handlers: list[Callable] = []
        self.orders_event_handlers: list[Callable] = []
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

    def __init_categories(self) -> None:
        """
        Загружает данные о категориях аккаунта + восстанавливает game_id каждой категории из кэша, либо
        отправляет дополнительные запросы к FunPay. (self.categories)

        :return: None
        """
        # Получаем категории аккаунта.
        while True:
            try:
                user_categories = FunPayAPI.users.get_user_categories(self.account.id)
                logger.info(f"Получил категории аккаунта. Всего категорий: {Fore.YELLOW}{len(user_categories)}.")
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
        # Так же добавляем game_id категории в self.game_ids
        logger.info("Получаю ID игр, к которым относятся категории...")
        cached_categories = cardinal_tools.load_cached_categories()
        for index, cat in enumerate(user_categories):
            cached_category_name = f"{cat.id}_{cat.type.value}"
            if cached_category_name in cached_categories:
                user_categories[index].game_id = cached_categories[cached_category_name]
                logger.info(f"Доп. данные о категории \"{cat.title}\" найдены в кэше.")
                continue

            logger.warning(f"Доп. данные о категории \"{cat.title}\" не найдены в кэше.")
            logger.info("Отправляю запрос к FunPay...")
            while True:
                try:
                    game_id = self.account.get_category_game_id(cat)
                    user_categories[index].game_id = game_id
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

        self.categories = user_categories
        logger.info("Кэширую данные о категориях...")
        cardinal_tools.cache_categories(self.categories)

    def __init_orders(self) -> None:
        """
        Загружает данные об ордерах пользователя.
        :return:
        """
        while True:
            try:
                self.processed_orders = self.account.get_account_orders()
                logger.info(f"Получил информацию об ордерах аккаунта.")
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
        self.message_event_handlers.append(self.log_msg)
        self.message_event_handlers.append(self.send_response_wrapper)
        self.message_event_handlers.append(self.send_command_notification)

    def __init_telegram(self) -> None:
        """
        Инициализирует Telegram бота.
        :return:
        """
        if int(self.main_config["Telegram"]["enabled"]):
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
                               f"Попробую еще раз через {response['wait']} секунд(-ы/-у).")
                logger.debug(response["response"])
                next_time = int(time.time()) + response["wait"]
                self.game_ids[cat.game_id] = next_time
                if min_next_time == -1 or next_time < min_next_time:
                    min_next_time = next_time
            else:
                for category_name in response["raised_category_names"]:
                    logger.info(f"Поднял категорию \"{category_name}\". ")
                logger.info(f"Все категории, относящиеся к игре с ID {cat.game_id} подняты!")
                logger.info(f"Попробую еще раз через {response['wait']} секунд(-ы/-у).")
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
        if not int(self.main_config["FunPay"]["autoRaise"]):
            return
        self.raise_lots_handlers.append(self.notify_categories_raised)
        logger.info("Авто-поднятие лотов запущено.")
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
        logger.info("Runner запущен.")
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
                    self.run_handlers(self.message_event_handlers, [event])

                elif event.type == FunPayAPI.enums.EventTypes.NEW_ORDER:
                    self.run_handlers(self.orders_event_handlers, [event])

    # Встроенные хэндлеры
    def send_response(self, msg: FunPayAPI.runner.MessageEvent):
        """
        Проверяет, является ли сообщение командой, если да - пытается отправить сообщение в ответ.
        :param msg: сообщение.
        :return:
        """
        if msg.message_text.strip() not in self.auto_response_config:
            return True
        logger.info(f"Получена команда \"{msg.message_text.strip()}\" "
                    f"в переписке с пользователем {Fore.YELLOW}{msg.sender_username} (node: {msg.node_id}).")

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
            logger.warning(f"Следующая попытка через 2 секунд.")
            time.sleep(2)
            return False

    def send_response_wrapper(self, msg: FunPayAPI.runner.MessageEvent):
        """
        Оболочка, обрабатывающая ошибки self.send_response(). Хэндлер.
        :param msg: сообщение.
        :return:
        """
        done = False
        attempts = 3
        while not done and attempts:
            try:
                result = self.send_response(msg)
            except:
                logger.warning(f"Произошла непредвиденная ошибка при отправке сообщения пользователю "
                               f"{msg.sender_username}.",)
                logger.debug(traceback.format_exc())
                logger.warning("Следующая попытка через 2 секунды.")
                attempts -= 1
                time.sleep(2)
                continue
            if not result:
                attempts -= 1
                continue
            done = True
        if not done:
            logger.error("Не удалось отправить ответ пользователю: превышено кол-во попыток.")
            return
        logger.debug("Response function complete.")

    def log_msg(self, msg: FunPayAPI.runner.MessageEvent):
        """
        Логирует полученное сообщение. Хэндлер.
        :param msg: сообщение.
        :return:
        """
        logger.info(f"Новое сообщение в переписке с пользователем {Fore.YELLOW}{msg.sender_username}"
                         f" (node: {msg.node_id}):")
        for line in msg.message_text.split("\n"):
            logger.info(line)

    def send_command_notification(self, msg: FunPayAPI.runner.MessageEvent):
        """
        Отправляет уведомление о введенной комманде в телеграм. Хэндлер.
        :param msg: сообщение с FunPay.
        :return:
        """
        if self.telegram is None or msg.message_text.strip() not in self.auto_response_config:
            return

        if int(self.auto_response_config[msg.message_text]["telegramNotification"]):
            if self.auto_response_config[msg.message_text].get("notificationText") is None:
                text = f"Пользователь {msg.sender_username} ввел команду \"{msg.message_text}\"."
            else:
                text = cardinal_tools.format_msg_text(self.auto_response_config[msg.message_text]["notificationText"],
                                                      msg)
            self.telegram.send_notification(text)

    def notify_categories_raised(self, game_id: int, category_names: list[str], wait_time: int) -> None:
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
        self.telegram.send_notification(f"Поднял категории: {cats_text}. (ID игры: {game_id}\n"
                                        f"Попробую еще раз через {wait_time} секунд(-ы/-у).")
        self.telegram.send_notification(cats_text)

    # Функции запуска / остановки Кардинала.
    def init(self):
        """
        Инициализирует все необходимые для работы Кардинала классы.
        :return:
        """
        self.__init_account()
        self.__init_categories()
        self.__init_orders()
        self.__init_runner()
        self.__init_telegram()

    def run(self):
        """
        Запускает все потоки.
        :return:
        """
        self.running = True
        Thread(target=self.lots_raise_loop).start()
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
    def run_handlers(self, handlers: list[Callable], *args) -> None:
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
