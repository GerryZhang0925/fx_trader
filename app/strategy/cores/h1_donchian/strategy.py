"""H1 20-bar channel break + ATR trail. Explore; not the live H4 Donchian pin."""

from __future__ import annotations

from strategy.cores.donchian.strategy import DonchianParams, DonchianStrategy

H1_DONCHIAN_DEFAULTS = dict(
    length=20,
    ema_len=200,
    atr_len=14,
    atr_mult=2.5,
    swing_len=5,
    stop_buffer_atr=0.5,
    use_adx_filter=False,
    use_atr_filter=False,
    partial_frac=0.0,
    partial_r=1.0,
    exit_on_opposite_break=True,
    exit_on_ema_flip=False,
    take_profit_r=None,
)


def h1_donchian_params(data: dict | None = None) -> DonchianParams:
    merged = {**H1_DONCHIAN_DEFAULTS, **(data or {})}
    return DonchianParams.from_dict(merged)


class H1DonchianStrategy(DonchianStrategy):
    name = "h1_donchian"

    def __init__(self, params: DonchianParams | None = None, **kwargs):
        if params is None:
            params = h1_donchian_params(kwargs)
        super().__init__(params)
