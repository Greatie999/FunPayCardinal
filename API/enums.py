from enum import Enum


class Links:
    BASE_URL = "https://funpay.com/"
    ORDERS = "https://funpay.com/orders/trade"
    RUNNER = "https://funpay.com/runner/"


class OrderStatuses(Enum):
    OUTSTANDING = 0
    COMPLETED = 1
    REFUND = 2
