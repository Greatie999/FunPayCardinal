"""
В данном модуле описан класс лота FunPay.
"""


class Lot:
    """
    Класс, описывающий лот.
    """
    def __init__(self,
                 category_id: int,
                 game_id: int | None,
                 id_: int,
                 server: str | None,
                 title: str,
                 price: str):
        """
        :param category_id: ID категории, к которой относится лот.
        :param game_id: ID игры, к которой относится лот.
        :param id_: ID лота.
        :param server: название сервера игры.
        :param title: название лота.
        :param price: цена лота.
        """
        self.category_id = category_id
        self.game_id = game_id
        self.id = id_
        self.server = server
        self.title = title
        self.price = price
