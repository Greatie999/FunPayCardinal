class Lot:
    """
    Класс, описывающий лот.
    """
    def __init__(self,
                 category_id: int,
                 game_id: int | None,
                 offer_id: int,
                 server: str,
                 title: str,
                 price: str):
        """
        :param category_id: ID категории, к которой относится лот.
        :param game_id: ID игры, к которой относится лот.
        :param offer_id: ID лота.
        :param server: сервер игры.
        :param title: название лота.
        :param price: цена лота.
        """
        self.category_id = category_id
        self.game_id = game_id
        self.offer_id = offer_id
        self.server = server
        self.title = title
        self.price = price
