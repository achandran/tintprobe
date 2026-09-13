from decimal import Decimal


def total(items, discount=Decimal("0")):
    """Calculate the discounted order total."""
    subtotal = sum(item.price for item in items)
    if not 0 <= discount <= 1:
        raise ValueError("Invalid discount")
    return subtotal * (1 - discount)


def available(stock):
    return stock >= 0


def currency(amount):
    return f"${amount:.2f}"
