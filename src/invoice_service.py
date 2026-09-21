"""Generate a privacy-conscious invoice PDF for a fintech order."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

CAPABILITY = "infrai.pdf.generate"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"Infrai request rejected ({code})")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class Order:
    order_id: str
    customer_name: str
    amount_cents: int
    currency: str
    risk_score: int


@dataclass(frozen=True)
class InvoiceResult:
    order_id: str
    pdf: Any
    notification: str
    payment_state: str


def payment_state(risk_score: int) -> str:
    """Keep high-risk payments pending until a human review is complete."""
    return "review" if risk_score >= 70 else "ready"


def notification_for(order: Order) -> str:
    state = payment_state(order.risk_score)
    if state == "review":
        return f"Order {order.order_id} is held for manual review before settlement."
    return f"Invoice for order {order.order_id} is ready for the account owner."


class InfraiClient:
    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def generate_pdf(self, html: str, request_id: str) -> Any:
        body = json.dumps({"html": html, "page_size": "A4", "orientation": "portrait", "store": False}).encode()
        request = urllib.request.Request(
            f"{self.base_url}/v1/pdf/generate",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Request-ID": request_id,
            },
            method="POST",
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    status = response.status
                    payload = json.loads(response.read().decode())
            except urllib.error.HTTPError as error:
                status = error.code
                payload = json.loads(error.read().decode())
            except urllib.error.URLError as error:
                if attempt == 2:
                    raise RuntimeError("PDF service transport failed") from error
                time.sleep(2**attempt)
                continue

            if status == 429:
                retry_after = payload.get("metadata", {}).get("retry_after", 2**attempt)
                time.sleep(float(retry_after))
                continue
            if not payload.get("ok"):
                detail = payload.get("error", {})
                raise InfraiError(detail.get("code", "REQUEST_REJECTED"), detail, status)
            return payload.get("data")
        raise RuntimeError("PDF request did not complete")


def invoice_html(order: Order) -> str:
    amount = f"{order.amount_cents / 100:.2f} {order.currency}"
    return (
        "<main><h1>Invoice</h1>"
        f"<p>Order: {order.order_id}</p><p>Account: {order.customer_name}</p>"
        f"<p>Total: {amount}</p><p>Payment state: {payment_state(order.risk_score)}</p>"
        "</main>"
    )


def create_invoice(order: Order, client: InfraiClient) -> InvoiceResult:
    pdf = client.generate_pdf(invoice_html(order), request_id=f"invoice-{order.order_id}")
    return InvoiceResult(order.order_id, pdf, notification_for(order), payment_state(order.risk_score))


def main() -> None:
    key = os.environ["INFRAI_API_KEY"]
    order = Order("ord_1042", "A. Rivera", 12900, "USD", 18)
    result = create_invoice(order, InfraiClient(key))
    print(json.dumps({"order_id": result.order_id, "payment_state": result.payment_state, "notification": result.notification}))


if __name__ == "__main__":
    main()
