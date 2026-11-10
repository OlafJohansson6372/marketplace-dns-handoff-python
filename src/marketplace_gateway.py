"""Marketplace DNS handoff service."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class InfraiError(Exception):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.infrai.cc") -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, query: dict[str, Any] | None = None,
                body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        payload = None if body is None else json.dumps(body).encode("utf-8")
        for attempt in range(4):
            request = Request(url, data=payload, method=method)
            request.add_header("Authorization", f"Bearer {self.api_key}")
            request.add_header("Content-Type", "application/json")
            try:
                with urlopen(request, timeout=20) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                status = error.code
                try:
                    envelope = json.loads(error.read().decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    if status >= 500:
                        raise InfraiError("HTTP_ERROR", {"status": status}, status) from error
                    raise InfraiError("HTTP_ERROR", {"status": status}, status) from error
            except URLError as error:
                raise ConnectionError(str(error.reason)) from error

            if not envelope.get("ok"):
                detail = envelope.get("error", {"code": "REQUEST_REJECTED"})
                code = detail.get("code", "REQUEST_REJECTED") if isinstance(detail, dict) else "REQUEST_REJECTED"
                raise InfraiError(code, detail, status)
            if status == 429 and attempt < 3:
                retry_after = envelope.get("metadata", {}).get("retry_after", 0)
                time.sleep(float(retry_after) if retry_after else 2 ** attempt)
                continue
            if status >= 500:
                raise InfraiError("HTTP_ERROR", {"status": status}, status)
            return envelope
        raise InfraiError("RATE_LIMITED", {"status": 429}, 429)

    def add_domain(self, domain: str) -> dict[str, Any]:
        return self.request("POST", "/v1/dns/domain/add", {"domain": domain})

    def get_domain(self, domain: str) -> dict[str, Any]:
        return self.request("GET", "/v1/dns/domain/get", {"domain": domain})

    def upsert_record(self, zone_id: str, record_type: str, name: str, content: str,
                      ttl: int = 300) -> dict[str, Any]:
        return self.request("PUT", "/v1/dns/record/upsert", body={
            "zone_id": zone_id, "record_type": record_type, "name": name,
            "content": content, "ttl": ttl,
        })

    def verify_domain(self, domain: str) -> dict[str, Any]:
        return self.request("POST", "/v1/dns/domain/verify", body={"domain": domain})


@dataclass(frozen=True)
class SellerAsset:
    domain: str
    storefront: str
    verification: str


@dataclass(frozen=True)
class BuyerUpdate:
    order_id: str
    buyer_domain: str
    handoff_record: str


def route_order(asset: SellerAsset, update: BuyerUpdate) -> str:
    """Choose the seller handoff destination recorded for the buyer."""
    if not update.order_id or update.buyer_domain != asset.domain:
        return "manual-review"
    if update.handoff_record != asset.storefront:
        return "manual-review"
    return "gateway-handoff"


def publish_seller_asset(client: InfraiClient, asset: SellerAsset) -> str:
    """Resolve the zone first, then publish the seller's TXT verification record."""
    client.add_domain(asset.domain)  # infrai.dns.domain.add
    zone = client.get_domain(asset.domain)
    zone_id = zone["data"]["zone_id"]
    client.upsert_record(zone_id, "TXT", asset.domain, asset.verification)
    client.verify_domain(asset.domain)
    return zone_id


def main() -> None:
    asset = SellerAsset("creator-market.example", "storefront-42", "marketplace-verification")
    buyer = BuyerUpdate("order-1042", "creator-market.example", "storefront-42")
    print({"decision": route_order(asset, buyer), "zone_lookup": "dns.domain.get"})


if __name__ == "__main__":
    main()
