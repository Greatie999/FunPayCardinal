import time
import configparser
from colorama import Fore, Back
from threading import Thread

import FunPayAPI.users
import FunPayAPI.account
import FunPayAPI.categories
from Utils.logger import Logger, LogTypes

import cardinal_tools


class Cardinal:
    def __init__(self,
                 main_config: configparser.ConfigParser,
                 lots_config: configparser.ConfigParser,
                 auto_response_config: configparser.ConfigParser,
                 auto_delivery_config: configparser.ConfigParser,
                 logger: Logger):

        # Перфиксы для логгера
        self.__CARDINAL_PREFIX = f"{Fore.BLACK}{Back.CYAN}[Cardinal]"

        # Конфиги
        self.main_config = main_config
        self.lots_config = lots_config
        self.auto_response_config = auto_response_config
        self.auto_delivery_config = auto_delivery_config

        # Логгер
        self.logger = logger

        # Прочее
        self.running = False
        self.account: FunPayAPI.account.Account | None = None

        # Категории
        self.categories: list[FunPayAPI.categories.Category] | None = None
        # ID игр категорий. Нужно для проверки возможности поднять ту или иную категорию.
        # Формат хранения: {ID игры: следующее время поднятия}
        self.game_ids = {}

    def init(self):
        self.__init_account()
        self.__init_categories()

    def __init_account(self):
        while True:
            try:
                self.account = FunPayAPI.account.get_account(self.main_config["Settings"]["token"])
                greeting_text = cardinal_tools.create_greetings(self.account)
                for line in greeting_text.split("\n"):
                    self.logger.log(line, self.__CARDINAL_PREFIX)
                break
            except TimeoutError:
                self.logger.log("Не удалось загрузить данные об аккаунте: превышен тайм-аут ожидания.",
                                self.__CARDINAL_PREFIX, LogTypes.ERROR)
                self.logger.log("Повторю попытку через 2 секунды...", self.__CARDINAL_PREFIX, LogTypes.WARN)
                time.sleep(2)
            # todo: добавить обработку других исключений

    def __init_categories(self) -> None:
        """
        Загружает данные о категориях аккаунта + восстанавливает game_id каждой категории из кэша, либо
        отправляет дополнительные запросы к FunPay.

        :return: None
        """
        cached_categories = cardinal_tools.load_cached_categories()
        # Получаем категории аккаунта.
        while True:
            try:
                user_categories = FunPayAPI.users.get_user_categories(self.account.id, include_currency=False)
                self.logger.log(f"Получил категории аккаунта. Всего категорий: {len(user_categories)}",
                                self.__CARDINAL_PREFIX)
                break
            except TimeoutError:
                self.logger.log("Не удалось загрузить данные о категориях аккаунта: превышен тайм-аут ожидания.",
                                self.__CARDINAL_PREFIX, LogTypes.ERROR)
                self.logger.log("Повторю попытку через 2 секунды...", self.__CARDINAL_PREFIX, LogTypes.WARN)
                time.sleep(2)
            # todo: добавить обработку других исключений

        # Привязываем к каждой категории её game_id. Если категория кэширована - берем game_id из кэша,
        # если нет - делаем запрос.
        # Так же добавляем game_id категории в self.game_ids
        self.logger.log("Получаю доп. данные о категориях...", self.__CARDINAL_PREFIX, LogTypes.WARN)
        for index, cat in enumerate(user_categories):
            cached_category_name = f"{cat.id}_{cat.type.value}"
            if cached_category_name in cached_categories:
                user_categories[index].game_id = cached_categories[cached_category_name]
                self.logger.log(f"Доп. данные о категории \"{cat.title}\" найдены в кэше! Как здорово!",
                                self.__CARDINAL_PREFIX)
                continue

            self.logger.log(f"Доп. данные о категории \"{cat.title}\" не найдены в кэше :(",
                            self.__CARDINAL_PREFIX, LogTypes.WARN)
            self.logger.log("Отправляю запрос к FunPay на получение доп. данных...",
                            self.__CARDINAL_PREFIX, LogTypes.WARN)
            while True:
                try:
                    game_id = self.account.get_category_game_id(cat)
                    user_categories[index].game_id = game_id
                    self.logger.log(f"Доп. данные о категории \"{cat.title}\" получены!",
                                    self.__CARDINAL_PREFIX)
                    break
                except TimeoutError:
                    self.logger.log(f"Не удалось загрузить доп. данные о категории \"{cat.title}\": "
                                    f"превышен тайм-аут ожидания.", self.__CARDINAL_PREFIX, LogTypes.ERROR)
                    self.logger.log("Повторю попытку через 2 секунды...", self.__CARDINAL_PREFIX, LogTypes.WARN)
                    time.sleep(2)

        self.categories = user_categories
        self.logger.log("Кэширую данные о категориях...", self.__CARDINAL_PREFIX, LogTypes.WARN)
        cardinal_tools.cache_categories(self.categories)

    def raise_lots(self) -> int:
        """
        Пытается поднять лоты.
        :return: предположительно время, когда нужно снова запустить данную функцию.
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
                self.logger.log(str(response), self.__CARDINAL_PREFIX, LogTypes.WARN)
                self.logger.log(str(response["response"]), self.__CARDINAL_PREFIX, LogTypes.WARN)
            except:
                min_next_time = int(time.time())
                continue
                # todo: добавить обработку исключений.
            if not response["complete"]:
                self.logger.log(f"Не удалось поднять категорию \"{cat.title}\". "
                                f"Попробую еще раз через {response['wait']} секунд(-ы/-у).", self.__CARDINAL_PREFIX,
                                LogTypes.WARN)
                next_time = int(time.time()) + response["wait"]
                self.game_ids[cat.game_id] = next_time
                if min_next_time == -1 or next_time < min_next_time:
                    min_next_time = next_time
            else:
                self.logger.log(f"Поднял все категории игры с ID \"{cat.game_id}\". "
                                f"Попробую еще раз через {response['wait']} секунд(-ы/-у). ", self.__CARDINAL_PREFIX)
                next_time = int(time.time()) + response['wait']
                self.game_ids[cat.game_id] = next_time
                if min_next_time == -1 or next_time < min_next_time:
                    min_next_time = next_time
        return min_next_time

    # Бесконечные циклы.
    def start_raise_lots_loop(self):
        """
        Запускает бесконечный цикл поднятия категорий (если autoRaise в _main.cfg == 1)
        :return:
        """
        if not int(self.main_config["Settings"]["autoRaise"]):
            return
        self.logger.log("Авто-поднятие лотов запущено.", self.__CARDINAL_PREFIX)
        while True and self.running:
            try:
                next_time = self.raise_lots()
            except:
                time.sleep(10)
                self.logger.log("err", self.__CARDINAL_PREFIX, LogTypes.ERROR)
                continue
            delay = next_time - int(time.time())
            if delay < 0:
                delay = 0
            time.sleep(delay)

    def run(self):
        """
        Запускает все потоки.
        :return:
        """
        self.running = True
        Thread(target=self.start_raise_lots_loop).start()

    def stop(self):
        """
        Останавливает все потоки.
        :return:
        """
        self.running = False
