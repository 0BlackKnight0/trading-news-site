# backend/tests/test_matching.py
import pathlib

from aggregator.matching import aliases_for, match_symbols


# --- aliases_for ------------------------------------------------------------

def test_aliases_for_reliance():
    # Bare "reliance" is an ambiguous, ordinary-English-word alias (see
    # test_ambiguous_aliases below) and is dropped once the more specific
    # "reliance industries" alias survives.
    assert aliases_for("RELIANCE.NS", "Reliance Industries Limited") == [
        "reliance industries",
    ]


def test_aliases_for_tcs():
    assert aliases_for("TCS.NS", "Tata Consultancy Services Limited") == [
        "tata consultancy services", "tcs",
    ]


def test_aliases_for_infosys():
    assert aliases_for("INFY.NS", "Infosys Limited") == ["infosys", "infy"]


def test_aliases_for_apple():
    assert aliases_for("AAPL", "Apple Inc.") == ["apple", "aapl"]


def test_aliases_for_nvidia():
    assert aliases_for("NVDA", "NVIDIA Corporation") == ["nvidia", "nvda"]


def test_aliases_for_none_long_name_returns_just_the_ticker():
    assert aliases_for("RELIANCE.NS", None) == ["reliance"]


def test_aliases_for_blank_long_name_returns_just_the_ticker():
    assert aliases_for("RELIANCE.NS", "   ") == ["reliance"]


def test_aliases_for_strips_exchange_suffixes():
    assert aliases_for("FOO.BO", None) == ["foo"]
    assert aliases_for("FOO.NSE", None) == ["foo"]
    assert aliases_for("FOO.BSE", None) == ["foo"]


def test_aliases_for_collapses_whitespace_and_lowercases():
    assert aliases_for("AAPL", "  Apple   Inc.  ") == ["apple", "aapl"]


def test_aliases_for_deduplicates_when_name_and_ticker_collide():
    # Long name reduces to the same string as the bare ticker.
    assert aliases_for("INFY", "Infy") == ["infy"]


# --- match_symbols: word-boundary anchoring ---------------------------------

def test_tcs_does_not_match_inside_outcomes():
    alias_map = {"TCS.NS": ["tata consultancy services", "tcs"]}
    assert match_symbols("Markets react to economic outcomes", alias_map) == []


def test_apple_does_not_match_inside_pineapple():
    alias_map = {"AAPL": ["apple", "aapl"]}
    assert match_symbols("Farmers report a strong pineapple harvest", alias_map) == []


def test_tcs_matches_as_a_whole_word():
    alias_map = {"TCS.NS": ["tata consultancy services", "tcs"]}
    assert match_symbols("TCS reports record quarterly profit", alias_map) == ["TCS.NS"]


def test_apple_matches_as_a_whole_word():
    alias_map = {"AAPL": ["apple", "aapl"]}
    assert match_symbols("Apple unveils its latest iPhone", alias_map) == ["AAPL"]


def test_match_is_case_insensitive():
    alias_map = {"AAPL": ["apple", "aapl"]}
    assert match_symbols("AAPL surges after earnings", alias_map) == ["AAPL"]


# --- match_symbols: general behaviour ---------------------------------------

def test_headline_matching_two_symbols_at_once():
    alias_map = {
        "TCS.NS": ["tata consultancy services", "tcs"],
        "INFY.NS": ["infosys", "infy"],
    }
    text = "TCS and Infosys both raise guidance for the quarter"
    assert match_symbols(text, alias_map) == ["TCS.NS", "INFY.NS"]


def test_each_matching_symbol_returned_at_most_once():
    alias_map = {"AAPL": ["apple", "aapl"]}
    text = "Apple's AAPL stock surges as Apple Inc posts record revenue"
    assert match_symbols(text, alias_map) == ["AAPL"]


def test_empty_text_returns_empty_list():
    alias_map = {"AAPL": ["apple", "aapl"]}
    assert match_symbols("", alias_map) == []


def test_none_text_returns_empty_list():
    alias_map = {"AAPL": ["apple", "aapl"]}
    assert match_symbols(None, alias_map) == []


def test_empty_alias_map_returns_empty_list():
    assert match_symbols("Apple reports record earnings", {}) == []


def test_no_match_returns_empty_list():
    alias_map = {"AAPL": ["apple", "aapl"]}
    assert match_symbols("Oil prices rally on OPEC cuts", alias_map) == []


# --- Purity ------------------------------------------------------------------

# --- Ambiguous aliases (false-positive guard) --------------------------------

def test_reliance_ns_drops_bare_alias_but_keeps_specific_one():
    assert aliases_for("RELIANCE.NS", "Reliance Industries Limited") == [
        "reliance industries",
    ]
    assert "reliance" not in aliases_for("RELIANCE.NS", "Reliance Industries Limited")


def test_real_false_positive_sentence_does_not_match_reliance():
    alias_map = {
        "RELIANCE.NS": aliases_for("RELIANCE.NS", "Reliance Industries Limited"),
    }
    text = (
        "China expands currency swap with Egypt as trade ties reach new "
        "heights. Experts say any reduced reliance on the US dollar will "
        "not happen overnight."
    )
    assert match_symbols(text, alias_map) == []


def test_specific_name_mention_still_matches_reliance():
    alias_map = {
        "RELIANCE.NS": aliases_for("RELIANCE.NS", "Reliance Industries Limited"),
    }
    assert match_symbols("Reliance Industries posts Q2 profit", alias_map) == [
        "RELIANCE.NS",
    ]


def test_symbol_whose_only_alias_is_ambiguous_keeps_it():
    # No long name, and the bare ticker itself happens to be an ambiguous
    # word — dropping it would leave zero aliases, which is worse than an
    # occasional false positive, so it is kept.
    assert aliases_for("GAP", None) == ["gap"]


def test_apple_alias_is_not_filtered():
    # Deliberately not in _AMBIGUOUS_ALIASES: "Apple" overwhelmingly means
    # Apple Inc. in a market-news corpus.
    assert aliases_for("AAPL", "Apple Inc.") == ["apple", "aapl"]


def test_matching_module_imports_nothing_impure():
    """This module must stay pure: no I/O, no clock, no database."""
    banned = ("import requests", "from database", "import database",
              "datetime.now", "from supabase")
    source = (pathlib.Path(__file__).parent.parent / "aggregator" / "matching.py").read_text()
    for token in banned:
        assert token not in source, f"matching.py must stay pure, found: {token}"
