from __future__ import annotations

import math


def sma(values: list[float], window: int) -> float | None:
    if window <= 0 or len(values) < window:
        return None
    return sum(values[-window:]) / window


def ema_series(values: list[float], span: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (span + 1)
    output = [values[0]]
    for value in values[1:]:
        output.append(value * alpha + output[-1] * (1 - alpha))
    return output


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for index in range(len(values) - period, len(values)):
        change = values[index] - values[index - 1]
        if change >= 0:
            gains += change
        else:
            losses += -change
    average_gain = gains / period
    average_loss = losses / period
    if average_loss == 0:
        return 100.0
    rs = average_gain / average_loss
    return 100 - 100 / (1 + rs)


def bollinger(
    values: list[float], period: int = 20, width: float = 2.0
) -> tuple[float, float, float] | None:
    if len(values) < period:
        return None
    window = values[-period:]
    middle = sum(window) / period
    variance = sum((value - middle) ** 2 for value in window) / period
    deviation = math.sqrt(variance)
    return middle - width * deviation, middle, middle + width * deviation


def macd(
    values: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[float, float, float] | None:
    if len(values) < slow + signal:
        return None
    fast_ema = ema_series(values, fast)
    slow_ema = ema_series(values, slow)
    dif = [fast_ema[index] - slow_ema[index] for index in range(len(values))]
    dea = ema_series(dif, signal)
    return dif[-1], dea[-1], dif[-1] - dea[-1]
