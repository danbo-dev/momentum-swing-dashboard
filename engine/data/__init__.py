"""Data-provider layer. Providers are swappable behind the base interfaces."""
from __future__ import annotations

from ..config import env, load_config
from .base import FundamentalProvider, PriceProvider


def get_price_provider(session=None) -> PriceProvider:
    """`session` pins every fetch to one trading session; see engine/session.py.
    Providers that don't consume it are unaffected (synthetic/tiingo are not
    session-sensitive today)."""
    cfg = load_config()
    name = cfg["data"]["price_provider"]
    if name == "polygon" and env("POLYGON_API_KEY"):
        from .polygon import PolygonProvider

        return PolygonProvider(session=session)
    if name == "tiingo" and env("TIINGO_API_KEY"):
        from .tiingo import TiingoProvider

        return TiingoProvider()
    # No key available -> synthetic so the pipeline still runs/verifies.
    from .synthetic import SyntheticProvider

    return SyntheticProvider()


def get_fundamental_provider() -> FundamentalProvider:
    if env("FINNHUB_API_KEY"):
        from .finnhub import FinnhubProvider

        return FinnhubProvider()
    from .synthetic import SyntheticProvider

    return SyntheticProvider()
