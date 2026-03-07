from typing import Any, Dict

import pandas as pd
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
    STRONG_SLOPE_PCT = 1.5
    FLAT_SLOPE_PCT = 0.6
    ABOVE_MA_BUFFER_PCT = 2.0
    NEAR_MA_BUFFER_PCT = 2.5

    STAGE_DEFINITIONS = {
        1: {
            "label": "ACCUMULATION",
            "title": "Stage 1: Accumulation",
            "summary": "30주선이 평탄해지거나 완만하게 돌아서며, 가격이 이동평균 부근에서 바닥을 다지는 구간입니다.",
            "checklist": [
                "가격이 30주선 부근에서 횡보합니다.",
                "하락 추세의 탄력이 약해집니다.",
                "추세 전환 전 준비 구간으로 해석합니다.",
            ],
        },
        2: {
            "label": "MARKUP",
            "title": "Stage 2: Markup",
            "summary": "가격이 30주선 위에서 유지되고, 30주선이 의미 있게 상승하는 추세 주도 구간입니다.",
            "checklist": [
                "가격이 30주선 위를 유지합니다.",
                "30주선 기울기가 상승 방향입니다.",
                "상대강도와 추세 지속 여부를 우선 확인합니다.",
            ],
        },
        3: {
            "label": "DISTRIBUTION",
            "title": "Stage 3: Distribution",
            "summary": "상승 추세가 둔화되며 30주선이 평탄해지고, 가격이 상단에서 분배 양상을 보일 수 있는 구간입니다.",
            "checklist": [
                "가격이 30주선 위 또는 부근에서 흔들립니다.",
                "30주선 상승 기울기가 둔화됩니다.",
                "돌파 실패와 거래량 분산을 경계합니다.",
            ],
        },
        4: {
            "label": "MARKDOWN",
            "title": "Stage 4: Markdown",
            "summary": "가격이 30주선 아래에서 머무르고, 30주선이 하락하는 하락 추세 구간입니다.",
            "checklist": [
                "가격이 30주선 아래에 위치합니다.",
                "30주선 기울기가 하락 방향입니다.",
                "반등보다 추세 전환 확인을 우선합니다.",
            ],
        },
    }

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
        ma_slope_pct = self._calculate_slope_pct(ma_30w)
        ma_slope = self._categorize_slope(ma_slope_pct)
        distance_to_ma = ((close - ma_30w) / ma_30w) * 100

        # Determine stage
        stage = self._determine_stage(close, ma_30w, ma_slope_pct)

        # Calculate stage labels
        stage_labels = stage.apply(self._get_stage_labels)

        return {
            "ma_30w": ma_30w,
            "ma_slope": ma_slope,
            "ma_slope_pct": ma_slope_pct,
            "distance_to_ma": distance_to_ma,
            "stage": stage,
            "stage_label": stage_labels,
        }

    def _calculate_slope_pct(self, ma_series: pd.Series, window: int = 4) -> pd.Series:
        base = ma_series.shift(window)
        return ((ma_series - base) / base) * 100

    def _categorize_slope(self, slope_pct: pd.Series) -> pd.Series:
        slopes = pd.Series(index=slope_pct.index, dtype=object)
        for index, value in slope_pct.items():
            if pd.isna(value):
                slopes.loc[index] = None
            elif value >= self.FLAT_SLOPE_PCT:
                slopes.loc[index] = "RISING"
            elif value <= -self.FLAT_SLOPE_PCT:
                slopes.loc[index] = "FALLING"
            else:
                slopes.loc[index] = "FLAT"
        return slopes

    def _determine_stage(
        self,
        close: pd.Series,
        ma: pd.Series,
        slope_pct: pd.Series,
    ) -> pd.Series:
        """
        Determine Weinstein stage

        Args:
            close: Close price series
            ma: Moving average series
            slope_pct: MA slope in percent

        Returns:
            Series with stage values (1, 2, 3, 4)
        """
        stages = pd.Series(index=close.index, dtype=int)

        for i in range(len(close)):
            if pd.isna(ma.iloc[i]) or pd.isna(slope_pct.iloc[i]):
                stages.iloc[i] = 0
                continue

            relative_to_ma = ((close.iloc[i] - ma.iloc[i]) / ma.iloc[i]) * 100
            slope_value = slope_pct.iloc[i]

            if (
                slope_value >= self.STRONG_SLOPE_PCT
                and relative_to_ma >= self.ABOVE_MA_BUFFER_PCT
            ):
                stages.iloc[i] = 2
            elif (
                slope_value <= -self.STRONG_SLOPE_PCT
                and relative_to_ma <= -self.ABOVE_MA_BUFFER_PCT
            ):
                stages.iloc[i] = 4
            elif relative_to_ma >= 0:
                stages.iloc[i] = 3
            else:
                stages.iloc[i] = 1

            if (
                abs(relative_to_ma) <= self.NEAR_MA_BUFFER_PCT
                and abs(slope_value) <= self.FLAT_SLOPE_PCT
            ):
                stages.iloc[i] = 3 if relative_to_ma >= 0 else 1

        return stages

    def _get_stage_labels(self, stage: int) -> str:
        """Get stage label from stage number"""
        return self.STAGE_DEFINITIONS.get(stage, {}).get("label", "UNKNOWN")

    def describe_stage(self, stage: int) -> Dict[str, Any]:
        return self.STAGE_DEFINITIONS.get(
            stage,
            {
                "label": "UNKNOWN",
                "title": "Stage Unknown",
                "summary": "충분한 데이터가 없어 Weinstein Stage를 해석할 수 없습니다.",
                "checklist": ["30주 이상 데이터가 필요한지 확인합니다."],
            },
        )

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
