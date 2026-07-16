"""Data-provider layer. Providers are swappable behind the base interfaces."""
from __future__ import annotations

from ..config import env, load_config
from .base import FundamentalProvider, PriceProvider


def get_price_provider() -> PriceProvider:
    cfg = load_config()
    name = cfg["data"]["price_provider"]
    if name == "polygon" and env("POLYGON_API_KEY"):
        from .polygon import PolygonProvider

        return PolygonProvider()
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
