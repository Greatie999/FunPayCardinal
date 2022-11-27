"""
В данном модуле написаны Enum-классы, которые используются другими модулями пакета FunPayAPI.
"""

from enum import Enum


class Links:
    """
    Основные ссылки для работы с FunPay API.
    """
    BASE_URL = "https://funpay.com"
    ORDERS = "https://funpay.com/orders/trade"
    USER = "https://funpay.com/users"
    RAISE = "https://funpay.com/lots/raise"
    RUNNER = "https://funpay.com/runner/"


class OrderStatuses(Enum):
    """
    Состояния ордеров.

    OrderStatuses.OUTSTANDING - ожидает выполнения.
    OrderStatuses.COMPLETED - выполнен.
    OrderStatuses.REFUND - запрошен возврат средств.
    """
    OUTSTANDING = 0
    COMPLETED = 1
    REFUND = 2


class CategoryTypes(Enum):
    """
    Типы лотов FunPay.

    CategoryTypes.LOT - стандартный лот.
    CategoryTypes.CURRENCY - лот с игровой валютой (их нельзя поднимать).
    """
    LOT = 0
    CURRENCY = 1


class EventTypes(Enum):
    """
    Типы эвентов.

    EventTypes.NEW_MESSAGE - новое сообщение.
    EventTypes.NEW_ORDER - изменение в ордерах.
    """
    NEW_MESSAGE = 0
    NEW_ORDER = 1
