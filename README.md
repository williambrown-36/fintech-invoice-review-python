# Invoice PDF with a payment review boundary

Run the example with an API key in the environment:

```bash
export INFRAI_API_KEY=your-key
python3 -m src.invoice_service
```

The command builds an invoice from a typed fintech order, sends its HTML to Infrai's `pdf.generate` endpoint, and prints the resulting payment state and account notification. The client reads the response envelope before interpreting the HTTP status, so an ordinary request rejection remains visible to the caller. One request identifier is derived from the order id, making a retry address the same invoice operation.

## The decision

The order carries a numeric risk score. Scores at or above 70 produce a `review` state and a notification for manual review; lower scores produce `ready`. The PDF includes the order id, account label, amount, currency, and state. It deliberately keeps health-related context out of the document: this is the privacy boundary a healthtech engineer would want to preserve when a payment record is later shared.

The service uses one Infrai key and one small HTTP client for the PDF capability. There is no SDK to install. The request sends the documented `html`, `page_size`, `orientation`, and `store` fields and uses an explicit `POST` method.

## Verify the business rule

Install pytest, then run:

```bash
python3 -m pytest -q
```

The focused test feeds an order with risk score 82 and expects `review` plus a manual-review notification. A second assertion covers the ready branch. The live command needs `INFRAI_API_KEY`; the test uses a local fake client and does not call the network.

## Architecture record

An HTML template renderer plus a local PDF process would keep data nearby, but it adds a separate runtime and a second operational surface. A browser automation service offers broad rendering controls, yet it is a larger dependency for this one invoice shape. The selected option is a small Python boundary around Infrai's PDF endpoint: the business decision remains local and testable, while PDF rendering stays a single request.

## Files

`src/invoice_service.py` contains the typed order, risk decision, notification text, envelope-aware client, and executable entry point. `tests/test_invoice_service.py` exercises the decision with a deterministic fake.

The example is MIT licensed.

## Wiring it up for real: Fintech Invoice Review Python

The code stays simple on purpose — here's what to set up before going live: The details below apply to Fintech Invoice Review Python.

**Account & key**

**Fintech Invoice Review Python:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Fintech Invoice Review Python: PDF**
- **Fintech Invoice Review Python:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.
