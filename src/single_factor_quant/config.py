"""Immutable configuration for the single-factor research workflow."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResearchConfig:
    """Validate and hold the shared research, portfolio, and cost parameters."""

    momentum_window: int = 252
    forward_horizon: int = 20
    quantiles: int = 5
    top_fraction: float = 0.20
    rebalance_interval: int = 20
    transaction_cost: float = 0.001
    winsor_lower: float = 0.01
    winsor_upper: float = 0.99
    annualization_days: int = 252

    def __post_init__(self) -> None:
        """Reject parameter values that make the configured calculations invalid."""
        _require_positive_int("momentum_window", self.momentum_window)
        _require_positive_int("forward_horizon", self.forward_horizon)
        _require_int_at_least("quantiles", self.quantiles, 2)
        _require_fraction("top_fraction", self.top_fraction, lower_open=True)
        _require_positive_int("rebalance_interval", self.rebalance_interval)
        _require_fraction("transaction_cost", self.transaction_cost, lower_open=False)
        if self.transaction_cost >= 0.5:
            raise ValueError("transaction_cost must be smaller than 0.5 for two-sided turnover")
        _require_fraction("winsor_lower", self.winsor_lower, lower_open=False)
        _require_fraction("winsor_upper", self.winsor_upper, lower_open=False)
        if self.winsor_lower >= self.winsor_upper:
            raise ValueError("winsor_lower must be smaller than winsor_upper")
        _require_positive_int("annualization_days", self.annualization_days)


def _require_positive_int(name: str, value: int) -> None:
    """Require an integer parameter greater than zero."""
    _require_int_at_least(name, value, 1)


def _require_int_at_least(name: str, value: int, minimum: int) -> None:
    """Require a non-boolean integer at or above a supplied lower bound."""
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer greater than or equal to {minimum}")


def _require_fraction(name: str, value: float, lower_open: bool) -> None:
    """Require a finite fraction in (0, 1] or [0, 1] as requested."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite fraction")
    if not float("-inf") < float(value) < float("inf"):
        raise ValueError(f"{name} must be a finite fraction")
    if value > 1.0 or value < 0.0 or (lower_open and value == 0.0):
        interval = "(0, 1]" if lower_open else "[0, 1]"
        raise ValueError(f"{name} must be in {interval}")
