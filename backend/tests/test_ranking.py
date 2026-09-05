# backend/tests/test_ranking.py
import pathlib

from aggregator.ranking import apply_scores, recency_bucket, score_article, source_weight

NOW = "2026-09-05T12:00:00+00:00"


def _item(title="A story", source="Reuters", published_at=NOW, symbol=None, url="http://a"):
    return {"title": title, "source": source, "published_at": published_at,
            "symbol": symbol, "url": url}


def test_source_weight_tiers():
    assert source_weight("Reuters") == 3
    assert source_weight("Economic Times") == 3
    assert source_weight("TechCrunch AI") == 2
    assert source_weight("Some Random Blog") == 1


def test_source_weight_is_case_insensitive():
    assert source_weight("reuters") == 3


def test_source_weight_handles_empty():
    assert source_weight("") == 1


def test_recency_buckets():
    assert recency_bucket("2026-09-05T11:00:00+00:00", NOW) == 3   # 1h
    assert recency_bucket("2026-09-05T04:00:00+00:00", NOW) == 2   # 8h
    assert recency_bucket("2026-09-04T06:00:00+00:00", NOW) == 1   # 30h
    assert recency_bucket("2026-09-01T00:00:00+00:00", NOW) == 0   # 4 days


def test_recency_bucket_for_undated_is_zero():
    assert recency_bucket(None, NOW) == 0


def test_recency_bucket_survives_an_unparseable_date():
    assert recency_bucket("not-a-date", NOW) == 0


def test_symbol_articles_score_higher_than_identical_ones_without():
    with_sym = score_article(_item(symbol="AAPL"), NOW)
    without = score_article(_item(symbol=None), NOW)
    assert with_sym == without + 2


def test_corroboration_adds_one_per_extra_source():
    assert score_article(_item(), NOW, corroboration=2) == score_article(_item(), NOW) + 2


def test_apply_scores_sets_a_score_on_every_item():
    items = apply_scores([_item(url="http://1"), _item(url="http://2")], NOW)
    assert all(isinstance(i["score"], int) for i in items)


def test_apply_scores_credits_corroboration_across_sources():
    """The same story from three outlets should outscore a lone report."""
    shared = "OPEC signals output cut"
    items = apply_scores([
        _item(title=shared, source="Reuters", url="http://1"),
        _item(title=shared + "!", source="Business Standard", url="http://2"),
        _item(title=shared.upper(), source="CNBC", url="http://3"),
        _item(title="Something else entirely", source="Reuters", url="http://4"),
    ], NOW)
    by_url = {i["url"]: i["score"] for i in items}
    assert by_url["http://1"] > by_url["http://4"]


def test_apply_scores_does_not_credit_one_source_repeating_itself():
    shared = "OPEC signals output cut"
    items = apply_scores([
        _item(title=shared, source="Reuters", url="http://1"),
        _item(title=shared, source="Reuters", url="http://2"),
    ], NOW)
    solo = apply_scores([_item(title=shared, source="Reuters", url="http://9")], NOW)
    assert items[0]["score"] == solo[0]["score"]


def test_apply_scores_handles_an_empty_batch():
    assert apply_scores([], NOW) == []


def test_ranking_module_is_pure():
    banned = ("import requests", "from database", "import database",
              "datetime.now", "from supabase")
    source = (pathlib.Path(__file__).parent.parent / "aggregator" / "ranking.py").read_text()
    for token in banned:
        assert token not in source, f"ranking.py must stay pure, found: {token}"
