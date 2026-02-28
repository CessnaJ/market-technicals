import pandas as pd
import numpy as np
from typing import Union


class MovingAverages:
    """
    Moving Averages Calculation

    Supports:
    - SMA: Simple Moving Average
    - EMA: Exponential Moving Average
    - VWMA: Volume Weighted Moving Average
    """

    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """
        Calculate Simple Moving Average

        Args:
            series: Price series
            period: Number of periods

        Returns:
            SMA series
        """
        return series.rolling(window=period).mean()

    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """
        Calculate Exponential Moving Average

        Args:
            series: Price series
            period: Number of periods

        Returns:
            EMA series
        """
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def vwma(close: pd.Series, volume: pd.Series, period: int) -> pd.Series:
        """
        Calculate Volume Weighted Moving Average

        VWMA = Sum(Price * Volume) / Sum(Volume)

        Args:
            close: Close price series
            volume: Volume series
            period: Number of periods

        Returns:
            VWMA series
        """
        pv = close * volume
        return pv.rolling(window=period).sum() / volume.rolling(window=period).sum()

    @staticmethod
    def calculate_all(
        df: pd.DataFrame,
        sma_periods: list = [5, 10, 20, 60, 120],
        ema_periods: list = [12, 26],
        vwma_periods: list = [5, 20],
    ) -> dict:
        """
        Calculate all moving averages

        Args:
            df: DataFrame with 'close' and 'volume' columns
            sma_periods: List of SMA periods
            ema_periods: List of EMA periods
            vwma_periods: List of VWMA periods

        Returns:
            Dictionary with all moving averages
        """
        result = {}

        # SMAs
        result["sma"] = {}
        for period in sma_periods:
            if len(df) >= period:
                result["sma"][str(period)] = MovingAverages.sma(df["close"], period)

        # EMAs
        result["ema"] = {}
        for period in ema_periods:
            if len(df) >= period:
                result["ema"][str(period)] = MovingAverages.ema(df["close"], period)

        # VWMAs
        result["vwma"] = {}
        for period in vwma_periods:
            if len(df) >= period:
                result["vwma"][str(period)] = MovingAverages.vwma(
                    df["close"], df["volume"], period
                )

        return result
