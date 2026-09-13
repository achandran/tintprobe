from decimal import Decimal


def total(items, discount=Decimal("0")):
    """Calculate the order total."""
    subtotal = sum(item.price for item in items)
    if discount > 1:
        raise ValueError("Invalid discount")
    return subtotal * (1 - discount)


def available(stock):
    return stock > 0
