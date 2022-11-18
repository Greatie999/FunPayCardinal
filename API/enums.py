from enum import Enum


class Links:
    BASE_URL = "https://funpay.com"
    ORDERS = "https://funpay.com/orders/trade"
    USER = "https://funpay.com/users"
    RUNNER = "https://funpay.com/runner"


class OrderStatuses(Enum):
    OUTSTANDING = 0
    COMPLETED = 1
    REFUND = 2


class CategoryTypes(Enum):
    LOT = 0
    CURRENCY = 1
