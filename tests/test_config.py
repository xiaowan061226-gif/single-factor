"""Stage-4 tests for immutable, validated project configuration."""

from dataclasses import FrozenInstanceError

import pytest

from single_factor_quant.config import ResearchConfig


def test_defaults_match_research_contract_and_are_immutable() -> None:
    config = ResearchConfig()

    assert config.momentum_window == 252
    assert config.forward_horizon == 20
    assert config.quantiles == 5
    assert config.top_fraction == 0.20
    assert config.rebalance_interval == 20
    assert config.transaction_cost == 0.001
    assert config.winsor_lower == 0.01
    assert config.winsor_upper == 0.99
    assert config.annualization_days == 252
    with pytest.raises(FrozenInstanceError):
        config.quantiles = 10  # type: ignore[misc]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"momentum_window": 0}, "momentum_window"),
        ({"forward_horizon": 0}, "forward_horizon"),
        ({"quantiles": 1}, "quantiles"),
        ({"top_fraction": 0.0}, "top_fraction"),
        ({"rebalance_interval": 0}, "rebalance_interval"),
        ({"transaction_cost": -0.01}, "transaction_cost"),
        ({"transaction_cost": 0.5}, "transaction_cost"),
        ({"momentum_window": True}, "momentum_window"),
        ({"forward_horizon": 2.5}, "forward_horizon"),
        ({"top_fraction": float("nan")}, "top_fraction"),
        ({"winsor_upper": float("inf")}, "winsor_upper"),
        ({"winsor_lower": 0.99, "winsor_upper": 0.01}, "winsor_lower"),
        ({"annualization_days": 0}, "annualization_days"),
    ],
)
def test_invalid_parameters_raise_clear_value_error(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        ResearchConfig(**kwargs)  # type: ignore[arg-type]
