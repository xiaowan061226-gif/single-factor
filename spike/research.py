"""Compatibility exports for stage-2 research probes.

The validated algorithms now live in the formal package. This module keeps the
old spike import paths and demos available without a second implementation.
"""

from single_factor_quant.preprocess.cross_section import cross_sectional_zscore
from single_factor_quant.research.grouping import QuintileResult, quintile_forward_returns
from single_factor_quant.research.ic import daily_ic_rankic, summarize_ic

__all__ = [
    "QuintileResult", "cross_sectional_zscore", "daily_ic_rankic",
    "quintile_forward_returns", "summarize_ic",
]
