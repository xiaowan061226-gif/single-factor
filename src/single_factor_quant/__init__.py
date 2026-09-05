"""Single-factor quantitative research project package."""

from .config import ResearchConfig
from .data import load_price_csv

__all__ = ["ResearchConfig", "load_price_csv"]
