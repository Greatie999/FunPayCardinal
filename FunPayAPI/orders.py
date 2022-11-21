from .enums import OrderStatuses


class Order:
    """
    Класс, описывающий заказ.
    """
    def __init__(self, id_: str, title: str, price: float, buyer_username: str, buyer_id: int, status: OrderStatuses):
        """
        :param id_: ID заказа.
        :param title: Краткое описание заказа.
        :param price: Оплаченная сумма за заказ.
        :param buyer_username: Псевдоним покупателя.
        :param buyer_id: ID покупателя.
        """
        self.id = id_
        self.title = title
        self.price = price
        self.buyer_name = buyer_username
        self.buyer_id = buyer_id
        self.status = status
