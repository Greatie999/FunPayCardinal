import os
import json
import time
import configparser
from colorama import Fore, Back, Style
from datetime import datetime

import API.users
import API.account
import API.categories
from Utils.logger import Logger, LogTypes


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
        self.account: API.account = None
        self.categories = None

    def init(self):
        self.__init_account()
        self.__init_categories()

    def __init_account(self):
        while True:
            try:
                self.account = API.account.get_account_data(self.main_config["Settings"]["token"])
                greeting_text = create_greetings(self.account)
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
        cached_categories = load_cached_categories()
        # Получаем категории аккаунта.
        while True:
            try:
                user_categories = API.users.get_user_categories(self.account.id, include_currency=False)
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
                    game_id = API.account.get_game_id_by_category_id(self.main_config["Settings"]["token"],
                                                                     cat.id, cat.type)
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
        cache_categories(self.categories)


    def run(self):
        self.running = True
        pass

    def stop(self):
        self.running = False
        pass


def cache_categories(category_list: list[API.categories.Category]) -> None:
    """
    Кэширует данные о категориях аккаунта в файл storage/cache/categories.json. Необходимо для того, чтобы каждый раз
    при запуске бота не отправлять запросы на получение game_id каждой категории.
    :param category_list: список категорий, которые необходимо кэшировать.
    :return: None
    """
    result = {}
    for cat in category_list:
        # Если у объекта категории game_id = None, то и нет смысла кэшировать данную категорию.
        if cat.game_id is None:
            continue

        # Имя категории для кэширования = id категории_тип категории (lot - 0, currency - 1).
        # Например:
        # 146_0 = https://funpay.com/lots/146/
        # 146_1 = https://funpay.com/chips/146/
        category_cached_name = f"{cat.id}_{cat.type.value}"
        result[category_cached_name] = cat.game_id

    # Создаем папку для хранения кэшированных данных.
    if not os.path.exists("storage/cache"):
        os.makedirs("storage/cache")

    # Записываем данные в кэш.
    with open("storage/cache/categories.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(result, indent=4))


def load_cached_categories() -> dict:
    """
    Загружает данные о категориях аккаунта из файла storage/cache/categories.json. Необходимо для того, чтобы каждый раз
    при запуске бота не отправлять запросы на получение game_id каждой категории.
    :return: словарь загруженных категорий.
    """
    if not os.path.exists("storage/cache/categories.json"):
        return {}

    with open("storage/cache/categories.json", "r", encoding="utf-8") as f:
        cached_categories = f.read()

    try:
        cached_categories = json.loads(cached_categories)
    except json.decoder.JSONDecodeError:
        return {}
    return cached_categories


def create_greetings(account: API.account):
    """
    Генерирует приветствие для вывода в консоль после загрузки данных о пользователе.
    :return:
    """
    current_time = datetime.now()
    if current_time.hour < 12:
        greetings = "Доброе утро"
    elif current_time.hour < 17:
        greetings = "Добрый день"
    elif current_time.hour < 24:
        greetings = "Добрый вечер"
    elif current_time.hour < 4:
        greetings = "Добрая ночь"
    else:
        greetings = "Доброе утро"

    currency = account.currency if f" {account.currency}" is not None else ""

    greetings_text = f"""{greetings}, {Fore.CYAN}{account.username}.
Ваш ID: {Fore.YELLOW}{account.id}.
Ваш текущий баланс: {Fore.YELLOW}{account.balance}{currency}.
Текущие незавершенные сделки: {Fore.YELLOW}{account.active_sales}.
{Fore.MAGENTA}Удачной торговли!"""
    return greetings_text
