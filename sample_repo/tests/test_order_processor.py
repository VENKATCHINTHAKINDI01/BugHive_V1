"""Existing tests for OrderProcessor — these all pass but miss the tax-on-discount bug."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.order_processor import OrderProcessor


def test_create_order():
    proc = OrderProcessor()
    order = proc.create_order("ORD-001", [{"name": "Widget", "price": 25.00, "quantity": 2}], "CUST-1")
    assert order["order_id"] == "ORD-001"
    assert order["status"] == "pending"


def test_calculate_total_no_discount():
    proc = OrderProcessor()
    proc.create_order("ORD-002", [{"name": "Widget", "price": 100.00, "quantity": 1}], "CUST-2")
    totals = proc.calculate_total("ORD-002")
    assert totals["subtotal"] == "100.00"
    assert totals["tax"] == "8.00"
    assert totals["total"] == "108.00"


def test_apply_discount_code():
    proc = OrderProcessor()
    proc.create_order("ORD-003", [{"name": "Gadget", "price": 50.00, "quantity": 1}], "CUST-3")
    order = proc.apply_discount("ORD-003", "SAVE10")
    assert order["discount_code"] == "SAVE10"


def test_invalid_discount_code():
    proc = OrderProcessor()
    proc.create_order("ORD-004", [{"name": "Gadget", "price": 50.00, "quantity": 1}], "CUST-4")
    try:
        proc.apply_discount("ORD-004", "FAKE99")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
