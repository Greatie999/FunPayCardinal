from dataclasses import dataclass

from .enums import OrderStatuses


@dataclass(frozen=True)
class Order:
    """
    Дата-класс, описывающий заказ.\n
    id: int - ID заказа.\n
    title: str - Краткое описание заказа.\n
    price: float - Оплаченная сумма за заказ.\n
    buyer_name: str - Псевдоним покупателя.\n
    buyer_id: int - ID покупателя.\n
    status: API.enums.OrderStatuses - статус выполнения заказа.\n
    """
    id: str
    title: str
    price: float
    buyer_name: str
    buyer_id: int
    status: OrderStatuses
