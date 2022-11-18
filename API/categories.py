from dataclasses import dataclass

from .enums import CategoryTypes


@dataclass(frozen=True)
class Category:
    """
    Дата-класс, описывающий категорию лотов.\n
    id: int - id пользователя.\n
    title: str - название категории.\n
    edit_lots_link: str - ссылка на лоты текущего аккаунта в данной категории .\n
    public_link: str - ссылка на все лоты всех пользователей в данной категории.\n
    type: API.enums.CategoryTypes - тип категории.\n
    """
    id: int
    title: str
    edit_lots_link: str
    public_link: str
    type: CategoryTypes
