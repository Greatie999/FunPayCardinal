"""
В этом модуле написаны функции для получения тех или иных данных о пользователе FunPay, для которых не требуется токен.
"""
from bs4 import BeautifulSoup
import requests

from .enums import Links, CategoryTypes
from .categories import Category


def get_user_categories(user_id: int, include_currency: bool = False, timeout: float = 10.0) -> list[Category]:
    """
    Получает список категорий лотов пользователя (кроме лотов с игровой валютой, т.к. лоты в категории игровой валюты
    нельзя поднять).

    :param user_id: ID пользователя, категории лотов которого нужно получить.
    :param include_currency: включить ли в возвращаемый список лоты с игровой валютой.
    :param timeout: тайм-аут ожидания ответа.
    :return: список категорий пользователя.
    """
    response = requests.get(f"{Links.USER}/{user_id}/", timeout=timeout)
    if response.status_code == 404:
        raise Exception  # todo: создать и добавить кастомное исключение: пользователя не существует.
    if response.status_code != 200:
        raise Exception  # todo: создать и добавить кастомное исключение: не удалось получить данные с сайта.

    html_response = response.content.decode()
    parser = BeautifulSoup(html_response, "lxml")
    categories = []

    category_divs = parser.find_all("div", {"class": "offer-list-title"})
    for div in category_divs:
        category_link = div.find("a")
        public_link = category_link["href"]
        if "chips" in public_link:
            # 'chips' в ссылке означает, что данная категория - игровая валюта.
            # Например: https://funpay.com/chips/125/ - Серебро Black Desert Mobile.
            if not include_currency:
                continue
            category_type = CategoryTypes.CURRENCY
        else:
            category_type = CategoryTypes.LOT

        edit_lots_link = public_link + "trade"
        title = category_link.text
        category_id = int(public_link.split("/")[-2])
        category_object = Category(id_=category_id, game_id=None, title=title, edit_lots_link=edit_lots_link,
                                   public_link=public_link, type_=category_type)
        categories.append(category_object)
    return categories
