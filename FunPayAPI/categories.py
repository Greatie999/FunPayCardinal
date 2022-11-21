from .enums import CategoryTypes


class Category:
    """
    Класс, описывающий категорию.
    """
    def __init__(self, id_: int, game_id: int | None, title: str, edit_lots_link: str, public_link: str,
                 type_: CategoryTypes):
        """
        :param id_: id категории.
        :param title: название категории.
        :param edit_lots_link: ссылка на страницу редактирования лотов данной категории.
        :param public_link: ссылка на все лоты всех пользователей в данной категории.
        :param type_: тип категории.
        """
        self.id = id_
        self.game_id = game_id
        self.title = title
        self.edit_lots_link = edit_lots_link
        self.public_link = public_link
        self.type = type_
