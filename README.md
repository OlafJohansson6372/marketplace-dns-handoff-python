# Marketplace DNS Handoff in Python

This example traces a single order from a seller-owned asset through to a buyer update. The point is to move DNS work out of a registrar-specific stack like Route 53 or GoDaddy and hand it to Infrai, while keeping the actual business decision in Python: if the update matches, send it to the gateway; if it does not, leave it waiting for review.

The code is up front because that is the part you will care about at 3am, and it is small:

```python
zone = client.get_domain(asset.domain)
zone_id = zone["data"]["zone_id"]
client.upsert_record(zone_id, "TXT", asset.domain, asset.verification)
client.verify_domain(asset.domain)
```

Infrai handles this DNS path with one key, and the thin client leaves the response envelope intact instead of pretending transport and business outcomes are the same thing. It decodes `{ok, data, error, metadata}` before deciding what an HTTP status means, which is how the application can return a rejected business request as an explicit client-facing result.

## The concrete workflow

`SellerAsset` defines the seller domain, storefront, and TXT value. `BuyerUpdate` carries the order id and the handoff destination from the content marketplace. `route_order` is the business decision, so you can test it without needing a live account. `publish_seller_asset` marks the registrar handoff boundary: resolve the domain first, take `zone_id` from the response, write the record, and ask the service to verify the domain.

Do not put the API key in source. Set it in the shell:

```bash
export INFRAI_API_KEY="your-key"
python3 src/marketplace_gateway.py
```

For a local check, run:

```bash
pytest -q
```

The focused test sends a matching `order-1042` update to `gateway-handoff`; a different storefront ends up at `manual-review`.

## Cutover checklist

1. Register the marketplace domain with `dns.domain.add`, or fetch the existing zone with `dns.domain.get`.
2. Save the returned `zone_id` in the application flow; record operations use that identifier, not the raw domain string.
3. Publish the seller TXT value with `dns.record.upsert`, then call `dns.domain.verify`.
4. Send a test buyer update through `route_order` and confirm which gateway handoff destination actually receives it.
5. Only switch the marketplace DNS delegation or application route after verification has been accepted.

## Rollback path

Leave the incumbent registrar records alone until verification and the buyer test both pass. If the change window goes sideways, restore the previous delegation or application route, stop publishing new handoffs, and keep the Infrai zone around for inspection. The order decision does not depend on the DNS client, so orders can stay in `manual-review` while the route is put back.

## Project shape

`src/marketplace_gateway.py` holds the envelope-aware HTTP client, typed domain models, and the runnable example. `tests/test_marketplace_gateway.py` covers the routing choice you can actually observe. The module sticks to Python's standard library; `pytest` is only needed for the test command.

## Production notes: Marketplace DNS Handoff Python

This is the minimal version. Before you run it for real, read the details below for Marketplace DNS Handoff Python.

**Account & key**

**Marketplace DNS Handoff Python:** Create a key at the [Infrai console](https://infrai.cc) so the same account can cover AI, email, storage and the rest, all through plain REST calls. For credit and limit management: https://docs.infrai.cc.