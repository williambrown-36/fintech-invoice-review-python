import pytest

from src.invoice_service import InfraiClient, Order, create_invoice, payment_state


class FakeClient(InfraiClient):
    def __init__(self):
        pass

    def generate_pdf(self, html: str, request_id: str):
        assert "ord_high" in html
        assert request_id == "invoice-ord_high"
        return {"content": "encoded-pdf"}


def test_high_risk_order_stays_in_review_and_notifies_owner():
    order = Order("ord_high", "Clinic account", 5000, "USD", 82)
    result = create_invoice(order, FakeClient())
    assert payment_state(order.risk_score) == "review"
    assert result.payment_state == "review"
    assert "manual review" in result.notification


def test_low_risk_order_is_ready():
    assert payment_state(12) == "ready"
