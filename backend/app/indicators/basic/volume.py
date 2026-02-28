import pandas as pd
import numpy as np


class Volume:
    """
    Volume Indicators

    Supports:
    - OBV: On-Balance Volume
    - Volume MA: Volume Moving Average
    """

    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Calculate On-Balance Volume

        OBV = Previous OBV + (Current Volume * Direction)
        Direction = 1 if Close > Previous Close else -1

        Args:
            close: Close price series
            volume: Volume series

        Returns:
            OBV series
        """
        direction = np.where(close.diff() > 0, 1, -1)
        obv = (direction * volume).cumsum()

        return pd.Series(obv, index=close.index)

    @staticmethod
    def volume_ma(volume: pd.Series, period: int) -> pd.Series:
        """
        Calculate Volume Moving Average

        Args:
            volume: Volume series
            period: Number of periods

        Returns:
            Volume MA series
        """
        return volume.rolling(window=period).mean()

    @staticmethod
    def calculate_all(
        df: pd.DataFrame,
        obv: bool = True,
        volume_ma_periods: list = [5, 20, 60],
    ) -> dict:
        """
        Calculate all volume indicators

        Args:
            df: DataFrame with 'close' and 'volume' columns
            obv: Whether to calculate OBV
            volume_ma_periods: List of volume MA periods

        Returns:
            Dictionary with all volume indicators
        """
        result = {}

        # OBV
        if obv:
            result["obv"] = Volume.obv(df["close"], df["volume"])

        # Volume MAs
        result["volume_ma"] = {}
        for period in volume_ma_periods:
            if len(df) >= period:
                result["volume_ma"][str(period)] = Volume.volume_ma(
                    df["volume"], period
                )

        return result
