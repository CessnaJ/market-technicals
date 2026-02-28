import pandas as pd
import numpy as np
from typing import Tuple


class Bands:
    """
    Band Indicators

    Supports:
    - Bollinger Bands
    - Keltner Channels
    """

    @staticmethod
    def bollinger(
        series: pd.Series,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands

        Middle Band = SMA(period)
        Upper Band = Middle + (StdDev * multiplier)
        Lower Band = Middle - (StdDev * multiplier)

        Args:
            series: Price series
            period: Number of periods (default: 20)
            std_dev: Standard deviation multiplier (default: 2.0)

        Returns:
            Tuple of (Upper, Middle, Lower) bands
        """
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()

        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        return upper, middle, lower

    @staticmethod
    def keltner(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        ema_period: int = 20,
        atr_period: int = 10,
        multiplier: float = 2.0,
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Keltner Channels

        Middle Line = EMA(close)
        Upper Channel = Middle + (ATR * multiplier)
        Lower Channel = Middle - (ATR * multiplier)

        ATR (Average True Range) measures volatility

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            ema_period: EMA period (default: 20)
            atr_period: ATR period (default: 10)
            multiplier: ATR multiplier (default: 2.0)

        Returns:
            Tuple of (Upper, Middle, Lower) channels
        """
        # Calculate EMA for middle line
        middle = close.ewm(span=ema_period, adjust=False).mean()

        # Calculate True Range
        tr1 = high - low.shift(1)
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Calculate ATR
        atr = tr.rolling(window=atr_period).mean()

        # Calculate Keltner channels
        upper = middle + (atr * multiplier)
        lower = middle - (atr * multiplier)

        return upper, middle, lower

    @staticmethod
    def calculate_all(
        df: pd.DataFrame,
        bb_period: int = 20,
        bb_std: float = 2.0,
        keltner_ema: int = 20,
        keltner_atr: int = 10,
        keltner_mult: float = 2.0,
    ) -> dict:
        """
        Calculate all band indicators

        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            bb_period: Bollinger period
            bb_std: Bollinger standard deviation multiplier
            keltner_ema: Keltner EMA period
            keltner_atr: Keltner ATR period
            keltner_mult: Keltner multiplier

        Returns:
            Dictionary with all band indicators
        """
        result = {}

        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = Bands.bollinger(
            df["close"], bb_period, bb_std
        )
        result["bollinger"] = {
            "upper": bb_upper,
            "middle": bb_middle,
            "lower": bb_lower,
        }

        # Keltner Channels
        k_upper, k_middle, k_lower = Bands.keltner(
            df["high"], df["low"], df["close"],
            keltner_ema, keltner_atr, keltner_mult
        )
        result["keltner"] = {
            "upper": k_upper,
            "middle": k_middle,
            "lower": k_lower,
        }

        return result
