# backend/aggregator/matching.py
"""Pure symbol/headline matching.

No I/O, no clock, no database — this module only turns Yahoo profile data
into lowercase aliases and checks whether those aliases appear in a piece of
text, word-boundary anchored so short tickers like "TCS" don't match inside
unrelated words like "outcomes".
"""
import re

_EXCHANGE_SUFFIXES = (".NS", ".BO", ".NSE", ".BSE")

# Corporate suffixes stripped off the end of a long name, longest first so a
# multi-word suffix like "Holdings" doesn't get shadowed by a shorter one.
# Each is matched with an optional trailing period.
_CORPORATE_SUFFIXES = (
    "Incorporated", "Corporation", "Holdings", "Limited",
    "Company", "Corp", "PLC", "Ltd", "Co", "SA", "NV", "AG", "Inc",
)

_SUFFIX_RE = re.compile(
    r"[,\s]+(?:" + "|".join(re.escape(s) for s in _CORPORATE_SUFFIXES) + r")\.?\s*$",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _bare_ticker(symbol: str) -> str:
    ticker = symbol
    for suffix in _EXCHANGE_SUFFIXES:
        if ticker.upper().endswith(suffix):
            ticker = ticker[: -len(suffix)]
            break
    return _normalize(ticker)


def aliases_for(symbol: str, long_name: str | None) -> list[str]:
    """Lowercase aliases for one symbol: a stripped long name plus the bare
    ticker. De-duplicated, no empty strings."""
    aliases: list[str] = []

    if long_name and long_name.strip():
        stripped = long_name
        # Corporate suffixes can stack (e.g. "X Holdings Inc."), so strip
        # repeatedly until nothing more comes off.
        while True:
            new_stripped = _SUFFIX_RE.sub("", stripped)
            if new_stripped == stripped:
                break
            stripped = new_stripped
        name_alias = _normalize(stripped)
        if name_alias:
            aliases.append(name_alias)

    ticker_alias = _bare_ticker(symbol)
    if ticker_alias:
        aliases.append(ticker_alias)

    # De-dupe while preserving order.
    seen = set()
    unique = []
    for alias in aliases:
        if alias and alias not in seen:
            seen.add(alias)
            unique.append(alias)
    return unique


def match_symbols(text: str, alias_map: dict[str, list[str]]) -> list[str]:
    """Symbols whose aliases appear (word-boundary anchored, case-insensitive)
    in `text`. Each matching symbol is returned at most once, in the
    alias_map's iteration order."""
    if not text:
        return []
    lower = text.lower()
    matches = []
    for symbol, aliases in alias_map.items():
        for alias in aliases:
            if not alias:
                continue
            if re.search(r"\b" + re.escape(alias) + r"\b", lower):
                matches.append(symbol)
                break
    return matches
