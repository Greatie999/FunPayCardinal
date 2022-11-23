import datetime
import time
import configparser
import traceback
from typing import Callable, Generator

from colorama import Fore
from threading import Thread

import FunPayAPI.users
import FunPayAPI.account
import FunPayAPI.categories
import FunPayAPI.runner
import FunPayAPI.enums
import logging

import cardinal_tools


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

        self.logger = logging.getLogger("FunPayBot.Cardinal")

        # Прочее
        self.running = False
        self.account: FunPayAPI.account.Account | None = None
        self.runner: FunPayAPI.runner.Runner | None = None

        # Категории
        self.categories: list[FunPayAPI.categories.Category] | None = None
        # ID игр категорий. Нужно для проверки возможности поднять ту или иную категорию.
        # Формат хранения: {ID игры: следующее время поднятия}
        self.game_ids = {}

        # Хэндлеры
        self.message_handlers: list[Callable] = []
        self.order_handlers: list[Callable] = []

    def __init_account(self) -> None:
        """
        Инициализирует класс аккаунта (self.account)
        """
        while True:
            try:
                self.account = FunPayAPI.account.get_account(self.main_config["Settings"]["token"])
                greeting_text = cardinal_tools.create_greetings(self.account)
                for line in greeting_text.split("\n"):
                    self.logger.info(line)
                break
            except TimeoutError:
                self.logger.warning("Не удалось загрузить данные об аккаунте: превышен тайм-аут ожидания.")
                self.logger.warning("Повторю попытку через 2 секунды...")
                time.sleep(2)
            except:
                self.logger.error("Не удалось загрузить данные об аккаунте: неизвестная ошибка.")
                self.logger.debug(traceback.format_exc())
                self.logger.warning("Повторю попытку через 2 секунды...")
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
                self.logger.info(f"Получил категории аккаунта. Всего категорий: {Fore.YELLOW}{len(user_categories)}.")
                break
            except TimeoutError:
                self.logger.warning("Не удалось загрузить данные о категориях аккаунта: превышен тайм-аут ожидания.")
                self.logger.warning("Повторю попытку через 2 секунды...")
                time.sleep(2)
            except:
                self.logger.error("Не удалось загрузить данные о категориях аккаунта: неизвестная ошибка.")
                self.logger.debug(traceback.format_exc())
                self.logger.warning("Повторю попытку через 2 секунды...")
                time.sleep(2)
            # todo: добавить обработку других исключений

        # Привязываем к каждой категории её game_id. Если категория кэширована - берем game_id из кэша,
        # если нет - делаем запрос к FunPay.
        # Так же добавляем game_id категории в self.game_ids
        self.logger.info("Получаю ID игр, к которым относятся категории...")
        cached_categories = cardinal_tools.load_cached_categories()
        for index, cat in enumerate(user_categories):
            cached_category_name = f"{cat.id}_{cat.type.value}"
            if cached_category_name in cached_categories:
                user_categories[index].game_id = cached_categories[cached_category_name]
                self.logger.info(f"Доп. данные о категории \"{cat.title}\" найдены в кэше.")
                continue

            self.logger.warning(f"Доп. данные о категории \"{cat.title}\" не найдены в кэше.")
            self.logger.info("Отправляю запрос к FunPay...")
            while True:
                try:
                    game_id = self.account.get_category_game_id(cat)
                    user_categories[index].game_id = game_id
                    self.logger.info(f"Доп. данные о категории \"{cat.title}\" получены!")
                    break
                except TimeoutError:
                    self.logger.warning(f"Не удалось получить ID игры, к которой относится категория \"{cat.title}\": "
                                        f"превышен тайм-аут ожидания.")
                    self.logger.warning("Повторю попытку через 2 секунды...")
                    time.sleep(2)
                except:
                    self.logger.error(f"Не удалось получить ID игры, к которой относится категория \"{cat.title}\": "
                                      f"неизвестная ошибка.")
                    self.logger.debug(traceback.format_exc())
                    self.logger.warning("Повторю попытку через 2 секунды...")
                    time.sleep(2)

        self.categories = user_categories
        self.logger.info("Кэширую данные о категориях...")
        cardinal_tools.cache_categories(self.categories)

    def __init_runner(self) -> None:
        """
        Инициализирует класс раннер'а (self.runner),
        Загружает плагины и добавляет хэндлеры в self.message_handlers и self.order_handlers
        """
        self.runner = FunPayAPI.runner.Runner(self.account)
        self.message_handlers.append(self.log_msg)
        self.message_handlers.append(self.send_response_wrapper)

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
                self.logger.debug(str(response))
            except:
                self.logger.error("Не удалось поднять категорию \"{cat.title}\": неизвестная ошибка.")
                self.logger.debug(traceback.format_exc())
                next_time = int(time.time()) + 10
                if min_next_time == -1 or next_time < min_next_time:
                    min_next_time = next_time
                continue
                # todo: добавить обработку исключений.
            if not response["complete"]:
                self.logger.warning(f"Не удалось поднять категорию \"{cat.title}\". "
                                    f"Попробую еще раз через {response['wait']} секунд(-ы/-у).")
                self.logger.debug(response["response"])
                next_time = int(time.time()) + response["wait"]
                self.game_ids[cat.game_id] = next_time
                if min_next_time == -1 or next_time < min_next_time:
                    min_next_time = next_time
            else:
                for category_name in response["raised_category_names"]:
                    self.logger.info(f"Поднял категорию \"{category_name}\". ")
                self.logger.info(f"Все категории, относящиеся к игре с ID {cat.game_id} подняты!")
                self.logger.info(f"Попробую еще раз через {response['wait']} секунд(-ы/-у).")
                next_time = int(time.time()) + response['wait']
                self.game_ids[cat.game_id] = next_time
                if min_next_time == -1 or next_time < min_next_time:
                    min_next_time = next_time
        return min_next_time

    # Бесконечные циклы.
    def lots_raise_loop(self):
        """
        Запускает бесконечный цикл поднятия категорий (если autoRaise в _main.cfg == 1)
        :return:
        """
        if not int(self.main_config["Settings"]["autoRaise"]):
            return
        self.logger.info("Авто-поднятие лотов запущено.")
        while True and self.running:
            try:
                next_time = self.raise_lots()
            except:
                self.logger.error("Не удалось поднять лоты: произошла неизвестная ошибка.")
                self.logger.debug(traceback.format_exc())
                self.logger.info("Попробую ")
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
                    int(self.main_config["Settings"]["autoResponse"]),
                    int(self.main_config["Settings"]["autoSell"])
                ]
        ):
            return None
        self.logger.info("Runner запущен.")
        while self.running:
            try:
                self.logger.debug("Итерация runner'а.")
                events = self.runner.get_updates()
                yield events
            except:
                self.logger.error("Не удалось получить список эвентов.")
                self.logger.debug(traceback.format_exc())
                yield []
            time.sleep(6)

    def run_handlers(self):
        """
        "Слушает" self.listen_runner(), запускает хэндлеры, привязанные к эвенту.
        :return:
        """
        for events in self.listen_runner():
            for event in events:
                if event.type == FunPayAPI.enums.EventTypes.NEW_MESSAGE:
                    for func in self.message_handlers:
                        try:
                            func(event)
                        except:
                            self.logger.error("Произошла непредвиденная ошибка при выполнении хэндлера.")
                            self.logger.debug(traceback.format_exc())

                elif event.type == FunPayAPI.enums.EventTypes.NEW_ORDER:
                    # todo: написать обработку эвентов типа NEW_ORDER
                    pass

    # Встроенные хэндлеры
    def send_response(self, msg: FunPayAPI.runner.MessageEvent):
        """
        Проверяет, является ли сообщение командой, если да - пытается отправить сообщение в ответ.
        :param msg: сообщение.
        :return:
        """
        if msg.message_text.strip() not in self.auto_response_config:
            return True
        self.logger.info(f"Получена команда \"{msg.message_text.strip()}\" "
                         f"в переписке с пользователем {Fore.YELLOW}{msg.sender_username} (node: {msg.node_id}).")

        date_obj = datetime.datetime.now()
        month_name = cardinal_tools.get_month_name(date_obj.month)
        date = date_obj.strftime("%d.%m.%Y")
        str_date = f"{date_obj.day} {month_name}"
        str_full_date = str_date + f" {date_obj.year} года"

        response_text = self.auto_response_config[msg.message_text.strip()]["response"]\
            .replace("$username", msg.sender_username) \
            .replace("$full_date_text", str_full_date) \
            .replace("$date_text", str_date) \
            .replace("$date", date)

        msg_object = FunPayAPI.runner.MessageEvent(msg.node_id,
                                                   response_text,
                                                   msg.sender_username,
                                                   msg.send_time,
                                                   msg.tag)

        response = self.account.send_message(msg.node_id, response_text)
        if response.get("response") and response.get("response").get("error") is None:
            self.runner.last_messages[msg.node_id] = msg_object
            self.logger.info(f"Отправил ответ пользователю {msg.sender_username}.")
            return True
        else:
            self.logger.warning(f"Произошла ошибка при отправке сообщения пользователю {msg.sender_username}.")
            self.logger.debug(f"{response}")
            self.logger.warning(f"Следующая попытка через 2 секунд.")
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
                self.logger.warning(f"Произошла непредвиденная ошибка при отправке сообщения пользователю "
                                    f"{msg.sender_username}.",)
                self.logger.debug(traceback.format_exc())
                self.logger.warning("Следующая попытка через 2 секунды.")
                attempts -= 1
                time.sleep(2)
                continue
            if not result:
                attempts -= 1
                continue
            done = True
        if not done:
            self.logger.error("Не удалось отправить ответ пользователю: превышено кол-во попыток.")
            return
        self.logger.debug("Response function complete.")

    def log_msg(self, msg: FunPayAPI.runner.MessageEvent):
        """
        Логирует полученное сообщение. Хэндлер.
        :param msg: сообщение.
        :return:
        """
        self.logger.info(f"Новое сообщение в переписке с пользователем {Fore.YELLOW}{msg.sender_username}"
                         f" (node: {msg.node_id}):")
        for line in msg.message_text.split("\n"):
            self.logger.info(line)

    # Функции запуска / остановки Кардинала.
    def init(self):
        """
        Инициализирует все необходимые для работы Кардинала классы.
        :return:
        """
        self.__init_account()
        self.__init_categories()
        self.__init_runner()

    def run(self):
        """
        Запускает все потоки.
        :return:
        """
        self.running = True
        Thread(target=self.lots_raise_loop).start()
        Thread(target=self.run_handlers).start()

    def stop(self):
        """
        Останавливает все потоки.
        :return:
        """
        self.running = False
