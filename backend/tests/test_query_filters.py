"""Smart query filters: reading price, brand and color from what shoppers type."""
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from api import query_understanding as qu
from src.search.query_filters import (
    BrandIndex, describe, has_brand, has_color, parse_color, parse_price, parse_query,
)


def catalog():
    products = []
    for index in range(6):
        products.append({"id": f"n{index}", "brand": "Nike", "title": f"Nike running shoe {index}"})
        products.append({"id": f"u{index}", "brand": "Under Armour", "title": f"Under Armour shirt {index}"})
        # Many products mention apples, few are Apple: "apple" alone is not a brand.
        products.append({"id": f"a{index}", "brand": "Apple", "title": f"Apple iPhone charger {index}"})
        for extra in range(3):
            products.append({"id": f"f{index}{extra}", "brand": "Orchard Co",
                             "title": f"Fresh apple juice {index}{extra}"})
        products.append({"id": f"g{index}", "brand": "Generic", "title": f"Plain mug {index}"})
    return products


@pytest.fixture(scope="module")
def brands():
    return BrandIndex(catalog())


# ---------------------------------------------------------------- price

@pytest.mark.parametrize("query, expected, text", [
    ("running shoes under $100", {"min": None, "max": 100, "currency": "USD"}, "running shoes"),
    ("saree under rs 2,000", {"min": None, "max": 2000, "currency": "INR"}, "saree"),
    ("headphones below 2k", {"min": None, "max": 2000, "currency": None}, "headphones"),
    ("mascara over 15 dollars", {"min": 15, "max": None, "currency": "USD"}, "mascara"),
    ("laptop between 300 and 500", {"min": 300, "max": 500, "currency": None}, "laptop"),
    ("phone case $10-$20", {"min": 10, "max": 20, "currency": "USD"}, "phone case"),
    ("desk lamp £40 to £25", {"min": 25, "max": 40, "currency": "GBP"}, "desk lamp"),
])
def test_price_phrases_become_filters_and_leave_the_search_text(query, expected, text):
    price, remaining = parse_price(query)
    assert {key: price[key] for key in expected} == expected
    assert remaining == text


@pytest.mark.parametrize("query", [
    "tent for up to 6 people",      # a count
    "kids shoes 2 to 4 years",      # an age range without "between" or currency
    "airpods max 2",                # a product name
    "ssd over 500 gb",              # a size
    "under armour shirt",           # a brand, not a price
])
def test_numbers_that_are_not_prices_are_left_alone(query):
    price, remaining = parse_price(query)
    assert price is None and remaining == query


def test_a_price_alone_keeps_its_text_so_there_is_something_to_search():
    parsed = parse_query("under $50")
    assert parsed["text"] == "under $50" and "price" not in parsed["filters"]


# ---------------------------------------------------------------- color

def test_one_clear_color_is_found_and_synonyms_match():
    assert parse_color("grey kitchen table") == {"value": "gray"}
    assert parse_color("black and white dress") is None  # two colors: leave it to search
    assert has_color({"title": "Kitchen table in gray oak"}, "gray")
    assert has_color({"title": "Grey sofa"}, "gray")
    assert not has_color({"title": "Blue sofa"}, "gray")


# ---------------------------------------------------------------- brand

def test_brands_come_from_the_catalog(brands):
    assert parse_query("nike running shoes", brands)["filters"]["brand"]["label"] == "Nike"
    assert parse_query("under armour shirt", brands)["filters"]["brand"]["label"] == "Under Armour"


def test_ambiguous_words_are_not_brands_unless_signalled(brands):
    assert "brand" not in parse_query("apple juice", brands)["filters"]
    signalled = parse_query("charger by apple", brands)
    assert signalled["filters"]["brand"]["label"] == "Apple"
    assert signalled["text"] == "charger apple"  # the cue word goes, the brand stays
    assert parse_query("apple brand charger", brands)["filters"]["brand"]["label"] == "Apple"


def test_accessory_and_compatibility_searches_do_not_force_a_brand(brands):
    assert "brand" not in parse_query("nike replacement laces", brands)["filters"]
    assert "brand" not in parse_query("shoe bag for nike", brands)["filters"]


def test_placeholder_brands_and_brand_prefixes_are_ignored(brands):
    assert "brand" not in parse_query("generic mug", brands)["filters"]
    assert "brand" not in parse_query("under $50 gifts", brands)["filters"]


def test_has_brand_matches_brand_field_or_title():
    assert has_brand({"brand": "Samsung Electronics"}, "samsung")
    assert not has_brand({"brand": "Samsonite"}, "samsung")
    assert has_brand({"title": "Sony WH-1000XM4 headphones"}, "sony")


def test_skip_keeps_the_words_and_drops_the_filter(brands):
    parsed = parse_query("black nike shoes under $90", brands, skip={"price", "color"})
    assert parsed["text"] == "black nike shoes under $90"
    assert set(parsed["filters"]) == {"brand"}
    assert describe(parse_query("black nike shoes under $90", brands)["filters"]) == [
        {"type": "price", "label": "Under $90"},
        {"type": "brand", "label": "Nike"},
        {"type": "color", "label": "Black"},
    ]


# ---------------------------------------------------------------- applying them

SHOP_RESULTS = [
    {"title": "Black Nike Pegasus", "brand": "Nike", "price": 89, "currency": "USD"},
    {"title": "White Nike Air", "brand": "Nike", "price": 120, "currency": "USD"},
    {"title": "Black Adidas Runner", "brand": "adidas", "price": 70, "currency": "USD"},
    {"title": "Black Nike Revolution", "brand": "Nike", "price": 5000, "currency": "INR"},
    {"title": "Black Nike, price on request", "brand": "Nike", "price": None},
]


def titles(payload):
    return [item["title"] for item in payload["results"]]


def test_nothing_is_filtered_until_the_shopper_chooses_it(brands):
    understanding = qu.understand("black nike shoes under $100", "shops", brands)
    assert understanding["searchText"] == "black nike shoes"  # the price phrase still leaves the text
    assert understanding["price"]["available"] is True and understanding["price"]["applied"] is False
    assert [item["type"] for item in understanding["suggestions"]] == ["brand", "color"]
    payload = qu.apply({"results": SHOP_RESULTS}, understanding)
    assert titles(payload) == [item["title"] for item in SHOP_RESULTS]
    assert "warning" not in payload


def test_a_chosen_price_filters_shop_results(brands):
    understanding = qu.understand("black nike shoes under $100", "shops", brands, qu.FilterChoice(price=True))
    assert understanding["price"]["applied"] is True
    payload = qu.apply({"results": SHOP_RESULTS}, understanding)
    # Same currency and within budget; products without a price are left out.
    assert titles(payload) == ["Black Nike Pegasus", "Black Adidas Runner"]
    assert "USD" in payload["warning"]


def test_chips_the_shopper_chooses_filter_strictly(brands):
    understanding = qu.understand("black nike shoes under $100", "shops", brands,
                                   qu.FilterChoice(brand="nike", color="black", price=True))
    assert understanding["suggestions"] == []
    assert titles(qu.apply({"results": SHOP_RESULTS}, understanding)) == ["Black Nike Pegasus"]


def test_catalog_searches_cannot_apply_a_price(brands):
    understanding = qu.understand("nike shoes under $100", "mongo", brands, qu.FilterChoice(price=True))
    assert understanding["price"]["available"] is False and understanding["price"]["applied"] is False
    payload = qu.apply({"results": [{"title": "Nike shoe"}], "candidateCount": 1}, understanding)
    assert titles(payload) == ["Nike shoe"]


def test_plain_queries_leave_the_payload_unchanged():
    payload = {"results": [{"title": "Mug"}], "candidateCount": 1}
    assert qu.apply(payload, qu.understand("coffee mug", "mongo")) == payload


def test_brand_index_failure_never_breaks_search():
    assert qu.brand_index(Mock()) is None
    assert qu.brand_index(None) is None
    with patch.object(qu, "BrandIndex", side_effect=TypeError("bad catalog")):
        assert qu.brand_index([{"id": "x"}]) is None


# ---------------------------------------------------------------- API

def test_search_api_sends_clean_text_and_applies_chips(authenticated_api):
    from api import main

    engine = Mock()
    engine.products = catalog()
    engine.search.return_value = {"results": [
        {"id": "n1", "title": "Black Nike running shoe", "brand": "Nike"},
        {"id": "x1", "title": "Black trail shoe", "brand": "Merrell"},
    ], "candidateCount": 2}
    with patch.object(main.search_service, "_search_engine", engine), \
            patch.object(main, "search_initializing", return_value=False), \
            patch.object(main, "get_search_engine", return_value=engine), \
            patch.object(main, "with_product_links", side_effect=lambda payload: payload):
        client = TestClient(main.app)
        body = client.get("/api/search", params={"q": "black nike shoes under $100"}).json()
        assert engine.search.call_args.args[0] == "black nike shoes"  # price phrase removed
        assert engine.search.call_args.kwargs["limit"] == 20
        assert len(body["results"]) == 2
        assert {item["type"] for item in body["queryFilters"]["suggestions"]} == {"brand", "color"}

        body = client.get("/api/search", params={"q": "black nike shoes", "brand": "nike"}).json()
        assert engine.search.call_args.kwargs["limit"] == 500  # rank everything, then narrow
        assert [item["id"] for item in body["results"]] == ["n1"]
        assert body["queryFilters"]["active"] == [{"type": "brand", "value": "nike", "label": "Nike"}]

        client.get("/api/search", params={"q": "shoes under $100", "skip": "price,unknown"})
        assert engine.search.call_args.args[0] == "shoes under $100"


def test_the_price_chip_is_sent_as_a_query_parameter():
    assert qu.filter_choice().price is False
    assert qu.filter_choice(price="1").price is True
    assert qu.filter_choice(price="yes").price is False
