import pandas as pd
import numpy as np
from typing import Dict, Any
from app.indicators.basic.moving_average import MovingAverages


class WeinsteinAnalysis:
    """
    Stan Weinstein's 4-Stage Market Cycle Analysis

    Based on 30-week Moving Average

    Stages:
    - Stage 1 (BASING): 30-week MA stops falling, price consolidates
    - Stage 2 (ADVANCING): 30-week MA rising, price above MA
    - Stage 3 (TOPPING): 30-week MA flattens, volatility increases
    - Stage 4 (DECLINING): 30-week MA falling, price below MA

    Also calculates Mansfield Relative Strength
    """

    WEEKLY_MA_PERIOD = 30  # 30-week SMA

    def __init__(self, benchmark_ticker: str = "0001"):
        self.benchmark_ticker = benchmark_ticker

    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Perform Weinstein Stage Analysis

        Args:
            df: Weekly OHLCV DataFrame with 'close' column

        Returns:
            Dictionary with stage analysis results
        """
        if len(df) < self.WEEKLY_MA_PERIOD:
            return {}

        close = df["close"]

        # Calculate 30-week MA
        ma_30w = MovingAverages.sma(close, self.WEEKLY_MA_PERIOD)

        # Calculate MA slope
        ma_slope = self._calculate_slope(ma_30w)

        # Determine stage
        stage = self._determine_stage(close, ma_30w, ma_slope)

        # Calculate stage labels
        # stage_labels = self._get_stage_labels(stage) # FIXME: 삭제
        stage_labels = stage.apply(self._get_stage_labels)

        return {
            "ma_30w": ma_30w,
            "ma_slope": ma_slope,
            "stage": stage,
            "stage_label": stage_labels,
        }

    def _calculate_slope(self, ma_series: pd.Series, window: int = 4) -> pd.Series:
        """
        Calculate MA slope

        Returns:
            Series with slope values (RISING, FALLING, FLAT)
        """
        slopes = pd.Series(index=ma_series.index, dtype=object)

        for i in range(window, len(ma_series)):
            recent = ma_series.iloc[i - window : i]
            if len(recent) < 2:
                slopes.iloc[i] = "FLAT"
                continue

            # Calculate slope
            slope = (recent.iloc[-1] - recent.iloc[0]) / len(recent)

            if slope > 0.001:  # Threshold for rising
                slopes.iloc[i] = "RISING"
            elif slope < -0.001:  # Threshold for falling
                slopes.iloc[i] = "FALLING"
            else:
                slopes.iloc[i] = "FLAT"

        return slopes

    def _determine_stage(
        self,
        close: pd.Series,
        ma: pd.Series,
        slope: pd.Series,
    ) -> pd.Series:
        """
        Determine Weinstein stage

        Args:
            close: Close price series
            ma: Moving average series
            slope: MA slope series

        Returns:
            Series with stage values (1, 2, 3, 4)
        """
        stages = pd.Series(index=close.index, dtype=int)

        for i in range(len(close)):
            if pd.isna(ma.iloc[i]) or pd.isna(slope.iloc[i]):
                stages.iloc[i] = 0
                continue

            price_above_ma = close.iloc[i] > ma.iloc[i]
            ma_rising = slope.iloc[i] == "RISING"

            if ma_rising and price_above_ma:
                stages.iloc[i] = 2  # ADVANCING
            elif ma_rising and not price_above_ma:
                stages.iloc[i] = 3  # TOPPING
            elif not ma_rising and not price_above_ma:
                stages.iloc[i] = 4  # DECLINING
            else:
                stages.iloc[i] = 1  # BASING

        return stages

    def _get_stage_labels(self, stage: int) -> str:
        """Get stage label from stage number"""
        labels = {
            1: "BASING",
            2: "ADVANCING",
            3: "TOPPING",
            4: "DECLINING",
        }
        return labels.get(stage, "UNKNOWN")

    def detect_breakout(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect Stage 1 to Stage 2 breakout

        Criteria:
        - 30-week MA is rising
        - Price crosses above 30-week MA with volume

        Args:
            df: Weekly OHLCV DataFrame

        Returns:
            Dictionary with breakout detection result
        """
        result = self.analyze(df)

        if not result:
            return {
                "is_breakout": False,
                "confidence": 0.0,
            }

        ma_30w = result.get("ma_30w")
        stage = result.get("stage")
        ma_slope = result.get("ma_slope")

        if ma_30w is None:
            return {
                "is_breakout": False,
                "confidence": 0.0,
            }

        # Check for breakout conditions
        latest_ma_slope = ma_slope.iloc[-1] if len(ma_slope) > 0 else None

        is_breakout = (
            stage.iloc[-1] == 2  # Already in Stage 2
            or (latest_ma_slope == "RISING" and df["close"].iloc[-1] > ma_30w.iloc[-1])
        )

        # Calculate confidence based on volume
        if is_breakout:
            # Check if volume is above average
            avg_volume = df["volume"].rolling(window=10).mean().iloc[-1]
            current_volume = df["volume"].iloc[-1]

            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            confidence = min(1.0, 0.5 + (volume_ratio / 2))
        else:
            confidence = 0.0

        return {
            "is_breakout": is_breakout,
            "confidence": confidence,
            "volume_ratio": volume_ratio if is_breakout else None,
        }

    def calc_mansfield_rs(
        self,
        stock_weekly: pd.Series,
        benchmark_weekly: pd.Series,
    ) -> pd.Series:
        """
        Calculate Mansfield Relative Strength

        RS = (Stock / 52 weeks ago) - (Benchmark / 52 weeks ago)

        Positive = Outperforming benchmark
        Negative = Underperforming benchmark

        Args:
            stock_weekly: Stock weekly close prices
            benchmark_weekly: Benchmark weekly close prices

        Returns:
            Series with Mansfield RS values
        """
        # Calculate 52-week change
        stock_change = (stock_weekly / stock_weekly.shift(52)) - 1
        benchmark_change = (benchmark_weekly / benchmark_weekly.shift(52)) - 1

        # Mansfield RS
        mansfield_rs = stock_change - benchmark_change

        return mansfield_rs
