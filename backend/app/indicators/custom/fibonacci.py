import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple


class FibonacciRetracement:
    """
    Fibonacci Retracement Analysis

    Standard Levels:
    - 0.0% (swing high)
    - 23.6%
    - 38.2%
    - 50.0%
    - 61.8%
    - 78.6%
    - 100.0% (swing low)

    Extension Levels (for targets):
    - 127.2%
    - 161.8%
    - 200.0%
    - 261.8%
    """

    LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    EXTENSION_LEVELS = [1.272, 1.618, 2.0, 2.618]

    def __init__(self, lookback_days: int = 120):
        self.lookback_days = lookback_days

    def auto_detect(
        self,
        df: pd.DataFrame,
        trend: str = "UP",
    ) -> Dict[str, Any]:
        """
        Auto-detect swing high/low and calculate Fibonacci levels

        Args:
            df: Daily OHLCV DataFrame
            trend: 'UP' (uptrend) or 'DOWN' (downtrend)

        Returns:
            Dictionary with Fibonacci levels
        """
        if len(df) < self.lookback_days:
            return {}

        # Get lookback period
        lookback_df = df.tail(self.lookback_days)

        if trend == "UP":
            swing_high = lookback_df["high"].max()
            swing_low = lookback_df["low"].min()
        else:
            swing_high = lookback_df["high"].max()
            swing_low = lookback_df["low"].min()

        return self.calculate_levels(swing_low, swing_high)

    def calculate_levels(
        self,
        swing_low: float,
        swing_high: float,
    ) -> Dict[str, Any]:
        """
        Calculate Fibonacci retracement levels

        Args:
            swing_low: Swing low price
            swing_high: Swing high price

        Returns:
            Dictionary with Fibonacci levels
        """
        diff = swing_high - swing_low

        levels = {}
        for level in self.LEVELS:
            levels[str(level)] = swing_high - (diff * level)

        # Calculate extension levels
        extensions = {}
        for level in self.EXTENSION_LEVELS:
            if trend == "UP":
                # For uptrend, extensions are above swing high
                extensions[str(level)] = swing_high + (diff * level)
            else:
                # For downtrend, extensions are below swing low
                extensions[str(level)] = swing_low - (diff * level)

        return {
            "swing_low": swing_low,
            "swing_high": swing_high,
            "levels": levels,
            "extensions": extensions,
        }

    def find_confluence_zones(
        self,
        fib_levels: Dict[str, Any],
        ma_values: Dict[str, float],
        darvas_boxes: List[Dict[str, Any]],
        tolerance: float = 0.02,  # 2% tolerance
    ) -> List[Dict[str, Any]]:
        """
        Find confluence zones where multiple factors align

        Factors:
        - Fibonacci levels
        - Moving averages
        - Darvas box tops

        Args:
            fib_levels: Fibonacci levels dictionary
            ma_values: Dictionary of MA values
            darvas_boxes: List of Darvas boxes
            tolerance: Price tolerance for confluence (default: 2%)

        Returns:
            List of confluence zones sorted by strength
        """
        confluences = []

        # Get all price levels from different sources
        price_levels = []

        # Add Fibonacci levels
        for level, price in fib_levels.get("levels", {}).items():
            price_levels.append({
                "type": "fibonacci",
                "level": level,
                "price": price,
            })

        # Add MA levels
        for ma_name, price in ma_values.items():
            price_levels.append({
                "type": "ma",
                "name": ma_name,
                "price": price,
            })

        # Add Darvas box tops
        for box in darvas_boxes:
            if box.get("status") in ["ACTIVE", "BROKEN_UP"]:
                price_levels.append({
                    "type": "darvas_top",
                    "price": box.get("top"),
                })

        # Find confluences
        for i, level1 in enumerate(price_levels):
            matching = [level1]
            for level2 in price_levels[i + 1:]:
                price_diff = abs(level1["price"] - level2["price"])
                avg_price = (level1["price"] + level2["price"]) / 2
                if price_diff / avg_price <= tolerance:
                    matching.append(level2)

            if len(matching) >= 2:  # At least 3 levels confluence
                # Calculate zone range
                prices = [level1["price"]] + [m["price"] for m in matching]
                zone_min = min(prices)
                zone_max = max(prices)

                # Calculate strength (number of matching factors)
                strength = len(matching) + 1

                # Get component names
                components = [level1["type"]]
                for m in matching:
                    if m["type"] not in components:
                        components.append(m["type"])

                confluences.append({
                    "price_zone": (zone_min, zone_max),
                    "center": (zone_min + zone_max) / 2,
                    "strength": strength,
                    "components": components,
                })

        # Sort by strength descending
        confluences.sort(key=lambda x: x["strength"], reverse=True)

        return confluences
