import pandas as pd
import numpy as np
from typing import Dict, Any
from app.indicators.basic.moving_average import MovingAverages


class VPCI:
    """
    Volume Price Confirmation Indicator (VPCI)

    By Buff Dormeier

    VPCI = VPC * VPR * VM / Alpha

    Components:
    - VPC (Volume Price Confirmation/Contradiction): VWMA(long) - SMA(long)
      Positive: Volume confirms price trend
      Negative: Volume contradicts price trend

    - VPR (Volume Price Ratio): VWMA(short) / SMA(short)
      Short-term price-volume cohesion

    - VM (Volume Multiplier): VolumeMA(short) / VolumeMA(long)
      Recent volume explosion weighting

    - Alpha: Volatility smoothing coefficient
      Alpha = StdDev(close) / StdDev(volume)
    """

    def __init__(self, short_period: int = 5, long_period: int = 20):
        self.short_period = short_period
        self.long_period = long_period

    def calculate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate VPCI

        Args:
            df: DataFrame with 'close' and 'volume' columns

        Returns:
            Dictionary with VPCI components and values
        """
        if len(df) < self.long_period:
            return {}

        close = df["close"]
        volume = df["volume"]

        # Calculate VWMA and SMA for long period
        vwma_long = MovingAverages.vwma(close, volume, self.long_period)
        sma_long = MovingAverages.sma(close, self.long_period)

        # Calculate VWMA and SMA for short period
        vwma_short = MovingAverages.vwma(close, volume, self.short_period)
        sma_short = MovingAverages.sma(close, self.short_period)

        # Calculate VPC (Volume Price Confirmation/Contradiction)
        vpc = vwma_long - sma_long

        # Calculate VPR (Volume Price Ratio)
        vpr = vwma_short / sma_short

        # Calculate VM (Volume Multiplier)
        vol_ma_short = MovingAverages.volume_ma(volume, self.short_period)
        vol_ma_long = MovingAverages.volume_ma(volume, self.long_period)
        vm = vol_ma_short / vol_ma_long

        # Calculate Alpha (volatility smoothing)
        close_std = close.rolling(window=self.long_period).std()
        volume_std = volume.rolling(window=self.long_period).std()
        alpha = close_std / volume_std if volume_std != 0 else 1.0

        # Calculate VPCI
        vpci = (vpc * vpr * vm) / alpha

        # Determine signal
        signal = self._determine_signal(vpc, vpci)

        return {
            "vpci": vpci,
            "vpc": vpc,
            "vpr": vpr,
            "vm": vm,
            "alpha": alpha,
            "signal": signal,
        }

    def _determine_signal(self, vpc: pd.Series, vpci: pd.Series) -> pd.Series:
        """
        Determine VPCI signal

        Returns:
            Series with signal values
        """
        signals = pd.Series(index=vpc.index, dtype=object)

        for i in range(len(vpc)):
            if pd.isna(vpc.iloc[i]) or pd.isna(vpci.iloc[i]):
                signals.iloc[i] = "NEUTRAL"
            elif vpc.iloc[i] > 0:
                if vpci.iloc[i] > 0:
                    signals.iloc[i] = "CONFIRM_BULL"
                else:
                    signals.iloc[i] = "DIVERGE_BULL"
            else:  # vpc < 0
                if vpci.iloc[i] < 0:
                    signals.iloc[i] = "CONFIRM_BEAR"
                else:
                    signals.iloc[i] = "DIVERGE_BEAR"

        return signals

    def detect_false_breakout(
        self,
        df: pd.DataFrame,
        breakout_date: pd.Timestamp,
    ) -> Dict[str, Any]:
        """
        Detect false breakout at a specific date

        A breakout is considered false if:
        - Price is rising but VPCI is falling or negative

        Args:
            df: DataFrame with OHLCV data
            breakout_date: Date of breakout

        Returns:
            Dictionary with false breakout detection result
        """
        # Find the breakout date index
        breakout_idx = df.index.get_loc(breakout_date)

        if breakout_idx is None or breakout_idx < self.long_period:
            return {
                "is_false": False,
                "confidence": 0.0,
                "reason": "Insufficient data",
            }

        # Check VPCI trend before and after breakout
        vpci_series = self.calculate(df).get("vpci")

        if vpci_series is None:
            return {
                "is_false": False,
                "confidence": 0.0,
                "reason": "VPCI calculation failed",
            }

        vpci_before = vpci_series.iloc[breakout_idx - 1]
        vpci_after = vpci_series.iloc[breakout_idx]

        # Price rising but VPCI falling or negative = false breakout
        price_rising = df["close"].iloc[breakout_idx] > df["close"].iloc[breakout_idx - 1]

        is_false = price_rising and (vpci_after < vpci_before or vpci_after < 0)

        # Calculate confidence
        if is_false:
            confidence = 0.3  # Low confidence for false breakout
        else:
            confidence = 0.8  # High confidence for true breakout

        return {
            "is_false": is_false,
            "confidence": confidence,
            "reason": "VPCI divergence" if is_false else "VPCI confirmation",
        }

    def detect_divergence(
        self,
        df: pd.DataFrame,
        window: int = 20,
    ) -> list:
        """
        Detect price-VPCI divergence

        - Bullish Divergence: Price falling + VPCI rising
        - Bearish Divergence: Price rising + VPCI falling

        Args:
            df: DataFrame with OHLCV data
            window: Lookback window for divergence detection

        Returns:
            List of divergence signals
        """
        result = self.calculate(df)
        vpci_series = result.get("vpci")
        close_series = df["close"]

        if vpci_series is None:
            return []

        divergences = []

        for i in range(window, len(df)):
            # Check for bearish divergence (price up, VPCI down)
            price_trend = close_series.iloc[i] > close_series.iloc[i - window]
            vpci_trend = vpci_series.iloc[i] < vpci_series.iloc[i - window]

            if price_trend and vpci_trend:
                divergences.append({
                    "date": df.index[i],
                    "type": "BEARISH",
                    "price": close_series.iloc[i],
                    "vpci": vpci_series.iloc[i],
                    "strength": abs(vpci_series.iloc[i] - vpci_series.iloc[i - window]),
                })

            # Check for bullish divergence (price down, VPCI up)
            price_trend = close_series.iloc[i] < close_series.iloc[i - window]
            vpci_trend = vpci_series.iloc[i] > vpci_series.iloc[i - window]

            if price_trend and vpci_trend:
                divergences.append({
                    "date": df.index[i],
                    "type": "BULLISH",
                    "price": close_series.iloc[i],
                    "vpci": vpci_series.iloc[i],
                    "strength": abs(vpci_series.iloc[i] - vpci_series.iloc[i - window]),
                })

        return divergences
