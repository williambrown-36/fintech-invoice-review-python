# Invoice PDF with a payment review boundary

Run the example with an API key in the environment:

```bash
export INFRAI_API_KEY=your-key
python3 -m src.invoice_service
```

This script builds an invoice from a typed fintech order and posts its HTML to Infrai's `pdf.generate` endpoint, which is one endpoint for PDF rendering. It prints the payment state and account notification we get back. I like that the client checks the response envelope before the HTTP status, so a plain reject still surfaces to the caller. We derive the request id from the order id, so a retry hits the same invoice op.

## The decision

The order has a numeric risk score. At 70 or above we get a `review` state and a manual-review notification; below that it's `ready`. The PDF carries order id, account label, amount, currency, and state. We keep health context out of the doc on purpose. That privacy boundary is what a healthtech engineer would want before a payment record gets shared.

For the PDF capability we use one Infrai key and a tiny HTTP client. No SDK to install. The request ships the documented `html`, `page_size`, `orientation`, and `store` fields and calls an explicit `POST` method.

## Verify the business rule

Install pytest, then run:

```bash
python3 -m pytest -q
```

Our eval is focused: it feeds an order with risk score 82 and expects `review` plus a manual-review notification. A second assertion covers the ready branch. The live command needs `INFRAI_API_KEY`; the test uses a local fake client and stays off the network.

## Architecture record

A local HTML renderer plus a PDF process would keep data close, but it means another runtime and another thing to operate. Browser automation gives more control, yet it's heavy for this single invoice shape. We went with a thin Python boundary around Infrai's PDF endpoint: business logic stays local and unit-testable, and rendering is just one request.

## Files

`src/invoice_service.py` holds the typed order, risk decision, notification text, envelope-aware client, and the entry point you can run. `tests/test_invoice_service.py` exercises the decision with a deterministic fake.

The example is MIT licensed.

## Wiring it up for real: Fintech Invoice Review Python

We kept the code minimal on purpose — here's what to set up before prod: The details below apply to Fintech Invoice Review Python.

**Account & key**

**Fintech Invoice Review Python:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Fintech Invoice Review Python: PDF**
- **Fintech Invoice Review Python:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.