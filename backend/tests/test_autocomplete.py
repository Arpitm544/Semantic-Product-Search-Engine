"""Autocomplete: catalog phrase suggestions, brands, typos and the shopper's own history."""
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import PyMongoError

from api import suggestions as api_suggestions
from src.search.autocomplete import Autocomplete, normalize


def catalog():
    titles = [
        "Sony Wireless Headphones with Microphone", "Bose Wireless Headphones Noise Cancelling",
        "JBL Wireless Headphones Bluetooth", "Anker Wireless Headset for Office",
        "Logitech Wireless Headset Gaming", "Plantronics Wireless Headset Mono",
        "LEGO Star Wars Millennium Falcon", "LEGO Star Wars X-Wing", "LEGO Star Wars Death Star",
        "Steel Water Bottle", "Steel Water Bottle 1L", "Steel Water Bottle Kids",
        "Spigen Phone Case for iPhone 13", "OtterBox Phone Case for iPhone 12", "Caseology Phone Case for iPhone 11",
        "The North Face Jacket", "Nike Running Shoes",
    ]
    brands = ["Sony", "Bose", "JBL", "Anker", "Logitech", "Plantronics", "LEGO", "LEGO", "LEGO",
              "Hydro", "Hydro", "Hydro", "Spigen", "OtterBox", "Caseology", "The North Face", "Nike"]
    products = [{"id": str(i), "title": t, "brand": b} for i, (t, b) in enumerate(zip(titles, brands))]
    # Extra products so a few brands pass the minimum product count.
    products += [{"id": f"n{i}", "title": f"Nike Air Max {i}", "brand": "Nike"} for i in range(5)]
    products += [{"id": f"g{i}", "title": f"Plain mug {i}", "brand": "Generic"} for i in range(6)]
    return products


@pytest.fixture(scope="module")
def index():
    return Autocomplete(catalog())


def test_normalize_keeps_only_words_and_a_trailing_space():
    assert normalize("  Wireless,  HEADphones! ") == "wireless headphones "
    assert normalize("iPhone-13") == "iphone 13"
    assert normalize("") == ""


def test_completes_the_typed_words_as_one_phrase(index):
    # Equally common phrases: the shorter one comes first.
    assert index.complete("wireless he")[:2] == ["wireless headset", "wireless headphones"]
    # "lego st" continues "lego star", not unrelated words starting with "st" like "steel".
    suggestions = index.complete("lego st")
    assert "lego star wars" in suggestions and not any("steel" in s for s in suggestions)


def test_suggests_the_next_word_after_a_space_or_a_filler_word(index):
    assert "wireless headphones with microphone" not in index.complete("wireless headphones")
    assert index.complete("phone case for")[0] == "phone case for iphone"
    assert all(s.startswith("lego star wars ") for s in index.complete("lego star wars "))


def test_one_typo_in_the_word_being_typed_is_tolerated(index):
    assert index.complete("headphn")[0] == "headphones"
    assert index.complete("zzzzqq") == []


def test_short_input_and_exact_matches_give_nothing_new(index):
    assert index.complete("w") == []
    assert "lego star wars" not in index.complete("lego star wars")


def test_brands_need_enough_products_and_skip_placeholders(index):
    assert index.brand_matches("ni") == ["Nike"]
    assert index.brand_matches("gen") == []     # "Generic" is not a real brand
    assert index.brand_matches("so") == []      # Sony has too few products here


def test_merge_keeps_order_and_drops_repeats_ignoring_case():
    merged = api_suggestions.merge([("recent", ["Lego Star Wars"]), ("catalog", ["lego star wars", "lego star"])])
    assert merged == [{"text": "Lego Star Wars", "kind": "recent"}, {"text": "lego star", "kind": "catalog"}]


@pytest.fixture(autouse=True)
def empty_recent_cache():
    api_suggestions._recent.clear()
    yield
    api_suggestions._recent.clear()


def history(*queries):
    rows = MagicMock()
    rows.sort.return_value.limit.return_value = [{"query": query} for query in queries]
    collection = Mock()
    collection.find.return_value = rows
    return collection


def test_recent_matches_only_read_this_shoppers_history_and_match_by_words():
    collection = history("Lego Star Wars", "Lego Star Wars", "lego (city)", "wireless mouse")
    with patch.object(api_suggestions.search_history, "collection", return_value=collection):
        # Punctuation is ignored, repeats are dropped, newest first.
        assert api_suggestions.recent_matches("alice", "lego (") == ["Lego Star Wars", "lego (city)"]
    assert collection.find.call_args.args[0] == {"user_id": "alice"}


def test_recent_history_is_read_once_per_shopper_while_typing():
    collection = history("lego city", "lego star wars")
    with patch.object(api_suggestions.search_history, "collection", return_value=collection):
        for typed in ("le", "leg", "lego", "lego s"):
            api_suggestions.recent_matches("alice", typed)
        assert collection.find.call_count == 1
        api_suggestions.recent_matches("bob", "lego")
        assert collection.find.call_count == 2   # each shopper has their own history
    with patch.object(api_suggestions, "monotonic", return_value=10 ** 9):
        with patch.object(api_suggestions.search_history, "collection", return_value=collection):
            api_suggestions.recent_matches("alice", "lego")
    assert collection.find.call_count == 3       # read again once the cache expires


def test_recent_searches_failing_does_not_break_suggestions():
    with patch.object(api_suggestions.search_history, "collection", side_effect=PyMongoError("down")):
        assert api_suggestions.recent_matches("alice", "lego") == []


def test_one_suggestion_per_brand_keeps_the_plain_name():
    products = [{"id": f"s{i}", "title": f"Galaxy phone {i}", "brand": "Samsung Electronics"} for i in range(8)]
    products += [{"id": f"t{i}", "title": f"Galaxy tab {i}", "brand": "SAMSUNG"} for i in range(5)]
    assert Autocomplete(products).brand_matches("sam") == ["SAMSUNG"]


def test_suggest_endpoint_combines_recent_brand_and_catalog(authenticated_api):
    from api import main

    engine = Mock()
    engine.products = catalog()
    with patch.object(main.search_service, "_search_engine", engine), \
            patch.object(api_suggestions, "recent_matches", return_value=["nike air max 3"]):
        client = TestClient(main.app)
        body = client.get("/api/suggest", params={"q": "ni"}).json()
        kinds = [item["kind"] for item in body["suggestions"]]
        assert body["suggestions"][0] == {"text": "nike air max 3", "kind": "recent"}
        assert "brand" in kinds and "catalog" in kinds
        assert len(body["suggestions"]) <= 8
        assert client.get("/api/suggest", params={"q": "n"}).json()["suggestions"] == []


def test_suggest_endpoint_while_search_is_starting(authenticated_api):
    from api import main

    with patch.object(main.search_service, "_search_engine", None), \
            patch.object(api_suggestions, "recent_matches", return_value=["lego city"]):
        body = TestClient(main.app).get("/api/suggest", params={"q": "lego"}).json()
        assert body["suggestions"] == [{"text": "lego city", "kind": "recent"}]


def test_suggest_requires_sign_in():
    from api import main
    assert TestClient(main.app).get("/api/suggest", params={"q": "lego"}).status_code == 401
