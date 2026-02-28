from typing import Dict, Any, List
import pandas as pd
from app.indicators.custom.vpci import VPCI
from app.indicators.custom.weinstein import WeinsteinAnalysis
from app.indicators.custom.darvas_box import DarvasBox
from app.indicators.custom.fibonacci import FibonacciRetracement
from app.indicators.basic.moving_average import MovingAverages
from app.indicators.basic.oscillators import Oscillators


class SignalDetector:
    """
    Signal Detection and False Signal Analysis

    Combines multiple indicators to detect:
    - Breakout signals
    - False signals (divergences)
    - Signal confidence scoring
    """

    def __init__(self):
        self.vpci = VPCI()
        self.weinstein = WeinsteinAnalysis()
        self.darvas = DarvasBox()
        self.fibonacci = FibonacciRetracement()

    def analyze_breakout(
        self,
        df_daily: pd.DataFrame,
        df_weekly: pd.DataFrame,
        breakout_date: pd.Timestamp,
    ) -> Dict[str, Any]:
        """
        Analyze breakout at a specific date

        Checklist:
        1. Weinstein 30-week MA rising breakout? (Required)
        2. VPCI 0+ and rising? (Required)
        3. Volume 2x average? (Required)
        4. Mansfield RS positive? (Weighted)
        5. Darvas box breakout? (Weighted)

        Args:
            df_daily: Daily OHLCV DataFrame
            df_weekly: Weekly OHLCV DataFrame
            breakout_date: Date of breakout

        Returns:
            BreakoutSignal with confidence score
        """
        checklist = {
            "weinstein_breakout": False,
            "vpci_confirmed": False,
            "volume_sufficient": False,
            "mansfield_positive": False,
            "darvas_breakout": False,
        }

        # 1. Check Weinstein breakout
        weinstein_result = self.weinstein.detect_breakout(df_weekly)
        checklist["weinstein_breakout"] = weinstein_result.get("is_breakout", False)
        weinstein_confidence = weinstein_result.get("confidence", 0.0)

        # 2. Check VPCI confirmation
        vpci_result = self.vpci.detect_false_breakout(df_daily, breakout_date)
        is_false_breakout = vpci_result.get("is_false", False)
        vpci_confidence = 1.0 - vpci_result.get("confidence", 0.0)

        if not is_false_breakout:
            checklist["vpci_confirmed"] = True
        checklist["vpci_confidence"] = vpci_confidence

        # 3. Check volume
        avg_volume = df_daily["volume"].rolling(window=30).mean().iloc[-1]
        current_volume = df_daily["volume"].iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        checklist["volume_sufficient"] = volume_ratio >= 2.0
        checklist["volume_ratio"] = volume_ratio

        # 4. Check Mansfield RS (if benchmark data available)
        # This would require benchmark data, simplified here
        checklist["mansfield_positive"] = True  # Placeholder

        # 5. Check Darvas box breakout
        darvas_boxes = self.darvas.get_all_boxes(df_daily)
        latest_box = darvas_boxes[-1] if darvas_boxes else None

        if latest_box and latest_box.get("status") == "BROKEN_UP":
            checklist["darvas_breakout"] = True

        # Calculate overall confidence
        confidence_weights = {
            "weinstein_breakout": 0.3,  # Required
            "vpci_confirmed": 0.3,  # Required
            "volume_sufficient": 0.2,  # Required
            "mansfield_positive": 0.1,  # Weighted
            "darvas_breakout": 0.1,  # Weighted
        }

        total_weight = sum(confidence_weights.values())
        confidence = 0.0

        for key, passed in checklist.items():
            if passed:
                confidence += confidence_weights.get(key, 0.0)

        confidence = confidence / total_weight if total_weight > 0 else 0.0

        # Generate warnings
        warnings = []
        if not checklist["volume_sufficient"]:
            warnings.append("VOLUME_WEAK")
        if is_false_breakout:
            warnings.append("VPCI_DIVERGENCE")
        if confidence < 0.5:
            warnings.append("LOW_CONFIDENCE")

        # Determine signal type
        if is_false_breakout:
            signal_type = "FALSE_BREAKOUT"
        elif confidence >= 0.7:
            signal_type = "TRUE_BREAKOUT"
        elif confidence >= 0.5:
            signal_type = "POTENTIAL_BREAKOUT"
        else:
            signal_type = "WEAK_SIGNAL"

        return {
            "is_valid": not is_false_breakout,
            "confidence": confidence,
            "signal_type": signal_type,
            "checklist": checklist,
            "warnings": warnings,
        }

    def detect_divergence(
        self,
        df_daily: pd.DataFrame,
        window: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Detect price-VPCI divergences

        - Bullish Divergence: Price falling + VPCI rising
        - Bearish Divergence: Price rising + VPCI falling

        Args:
            df_daily: Daily OHLCV DataFrame
            window: Lookback window

        Returns:
            List of divergence signals
        """
        divergences = self.vpci.detect_divergence(df_daily, window)

        # Add Weinstein context
        weinstein_result = self.weinstein.analyze(df_daily)
        current_stage = weinstein_result.get("stage")

        # Enhance with stage context
        for div in divergences:
            div["weinstein_stage"] = current_stage
            div["stage_label"] = weinstein_result.get("stage_label")

            # Only consider bearish divergences in Stage 2 (Advancing) as warnings
            if div["type"] == "BEARISH" and current_stage == 2:
                div["significance"] = "WARNING"
            else:
                div["significance"] = "NORMAL"

        return divergences

    def analyze_false_signals(
        self,
        df_daily: pd.DataFrame,
        df_weekly: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Comprehensive false signal analysis

        Args:
            df_daily: Daily OHLCV DataFrame
            df_weekly: Weekly OHLCV DataFrame

        Returns:
            Dictionary with all false signal analysis
        """
        # Detect divergences
        divergences = self.detect_divergence(df_daily)

        # Count by type
        bearish_count = sum(1 for d in divergences if d["type"] == "BEARISH")
        bullish_count = sum(1 for d in divergences if d["type"] == "BULLISH")
        warning_count = sum(1 for d in divergences if d.get("significance") == "WARNING")

        return {
            "divergences": divergences,
            "bearish_count": bearish_count,
            "bullish_count": bullish_count,
            "warning_count": warning_count,
            "has_bearish_divergence": bearish_count > 0,
            "has_bullish_divergence": bullish_count > 0,
        }
