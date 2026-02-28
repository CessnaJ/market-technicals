import pandas as pd
import numpy as np
from typing import Tuple


class Oscillators:
    """
    Oscillator Indicators

    Supports:
    - RSI: Relative Strength Index
    - MACD: Moving Average Convergence Divergence
    - Stochastic: Stochastic Oscillator
    """

    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index

        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss

        Args:
            series: Price series
            period: Number of periods (default: 14)

        Returns:
            RSI series
        """
        delta = series.diff()

        # Separate gains and losses
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        # Calculate average gain and loss
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def macd(
        series: pd.Series,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence)

        MACD Line = EMA(fast) - EMA(slow)
        Signal Line = EMA(MACD)
        Histogram = MACD - Signal

        Args:
            series: Price series
            fast_period: Fast EMA period (default: 12)
            slow_period: Slow EMA period (default: 26)
            signal_period: Signal EMA period (default: 9)

        Returns:
            Tuple of (MACD, Signal, Histogram)
        """
        ema_fast = series.ewm(span=fast_period, adjust=False).mean()
        ema_slow = series.ewm(span=slow_period, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def stochastic(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = 14,
        d_period: int = 3,
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate Stochastic Oscillator

        %K = (Close - Lowest Low) / (Highest High - Lowest Low) * 100
        %D = SMA(%K)
        %D = SMA(%K, 3)

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            k_period: %K period (default: 14)
            d_period: %D period (default: 3)

        Returns:
            Tuple of (%K, %D)
        """
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()

        k_percent = 100 * (close - lowest_low) / (highest_high - lowest_low)
        d_percent = k_percent.rolling(window=d_period).mean()

        return k_percent, d_percent

    @staticmethod
    def calculate_all(
        df: pd.DataFrame,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        stoch_k: int = 14,
        stoch_d: int = 3,
    ) -> dict:
        """
        Calculate all oscillators

        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            rsi_period: RSI period
            macd_fast: MACD fast period
            macd_slow: MACD slow period
            macd_signal: MACD signal period
            stoch_k: Stochastic %K period
            stoch_d: Stochastic %D period

        Returns:
            Dictionary with all oscillators
        """
        result = {}

        # RSI
        result["rsi"] = Oscillators.rsi(df["close"], rsi_period)

        # MACD
        macd, signal, histogram = Oscillators.macd(
            df["close"], macd_fast, macd_slow, macd_signal
        )
        result["macd"] = {
            "macd": macd,
            "signal": signal,
            "histogram": histogram,
        }

        # Stochastic
        k, d = Oscillators.stochastic(df["high"], df["low"], df["close"], stoch_k, stoch_d)
        result["stochastic"] = {"k": k, "d": d}

        return result
