"""
Order Processing Module for BugHive Sample App.
Handles order creation, validation, discount application, and total calculation.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP


class OrderProcessor:
    """Processes customer orders with discount and tax logic."""

    TAX_RATE = Decimal("0.08")  # 8% tax
    MAX_DISCOUNT_PERCENT = Decimal("50.0")

    VALID_DISCOUNT_CODES = {
        "SAVE10": Decimal("10.0"),
        "SAVE20": Decimal("20.0"),
        "VIP30": Decimal("30.0"),
        "HALFOFF": Decimal("50.0"),
    }

    def __init__(self):
        self.orders = {}

    def create_order(self, order_id: str, items: list[dict], customer_id: str) -> dict:
        """
        Create a new order.
        Each item: {"name": str, "price": float, "quantity": int}
        """
        if not items:
            raise ValueError("Order must contain at least one item")

        order = {
            "order_id": order_id,
            "customer_id": customer_id,
            "items": items,
            "discount_code": None,
            "discount_percent": Decimal("0"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }
        self.orders[order_id] = order
        return order

    def apply_discount(self, order_id: str, discount_code: str) -> dict:
        """Apply a discount code to an existing order."""
        if order_id not in self.orders:
            raise KeyError(f"Order {order_id} not found")

        order = self.orders[order_id]

        if discount_code not in self.VALID_DISCOUNT_CODES:
            raise ValueError(f"Invalid discount code: {discount_code}")

        order["discount_code"] = discount_code
        order["discount_percent"] = self.VALID_DISCOUNT_CODES[discount_code]
        return order

    def calculate_total(self, order_id: str) -> dict:
        """
        Calculate the total for an order including discount and tax.

        BUG: When discount is applied, tax is calculated on the ORIGINAL subtotal
        instead of the DISCOUNTED subtotal. This overcharges the customer on tax.
        """
        if order_id not in self.orders:
            raise KeyError(f"Order {order_id} not found")

        order = self.orders[order_id]

        # Calculate subtotal
        subtotal = Decimal("0")
        for item in order["items"]:
            price = Decimal(str(item["price"]))
            quantity = Decimal(str(item["quantity"]))
            subtotal += price * quantity
            subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)   

        # Apply discount
        discount_amount = (subtotal * order["discount_percent"] / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        discounted_subtotal = subtotal - discount_amount

        # BUG IS HERE: tax is calculated on `subtotal` instead of `discounted_subtotal`
        tax = (subtotal * self.TAX_RATE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        total = discounted_subtotal + tax

        return {
            "order_id": order_id,
            "subtotal": str(subtotal),
            "discount_code": order["discount_code"],
            "discount_percent": str(order["discount_percent"]),
            "discount_amount": str(discount_amount),
            "discounted_subtotal": str(discounted_subtotal),
            "tax_rate": str(self.TAX_RATE),
            "tax": str(tax),
            "total": str(total),
        }

    def get_order_summary(self, order_id: str) -> str:
        """Return a human-readable order summary."""
        totals = self.calculate_total(order_id)
        lines = [
            f"Order: {totals['order_id']}",
            f"  Subtotal:    ${totals['subtotal']}",
            f"  Discount:    -{totals['discount_amount']} ({totals['discount_code'] or 'none'})",
            f"  After Disc:  ${totals['discounted_subtotal']}",
            f"  Tax (8%):    ${totals['tax']}",
            f"  Total:       ${totals['total']}",
        ]
        return "\n".join(lines)
