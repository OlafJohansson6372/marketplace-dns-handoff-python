from src.marketplace_gateway import BuyerUpdate, SellerAsset, route_order


def test_matching_buyer_update_is_sent_to_gateway() -> None:
    asset = SellerAsset("creator-market.example", "storefront-42", "marketplace-verification")
    update = BuyerUpdate("order-1042", "creator-market.example", "storefront-42")

    assert route_order(asset, update) == "gateway-handoff"


def test_mismatched_handoff_stays_for_manual_review() -> None:
    asset = SellerAsset("creator-market.example", "storefront-42", "marketplace-verification")
    update = BuyerUpdate("order-1042", "creator-market.example", "other-storefront")

    assert route_order(asset, update) == "manual-review"
