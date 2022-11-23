from enum import Enum


class Links:
    BASE_URL = "https://funpay.com"
    ORDERS = "https://funpay.com/orders/trade"
    USER = "https://funpay.com/users"
    RAISE = "https://funpay.com/lots/raise"
    RUNNER = "https://funpay.com/runner/"


class OrderStatuses(Enum):
    OUTSTANDING = 0
    COMPLETED = 1
    REFUND = 2


class CategoryTypes(Enum):
    LOT = 0
    CURRENCY = 1


class EventTypes(Enum):
    NEW_MESSAGE = 0
    NEW_ORDER = 0
