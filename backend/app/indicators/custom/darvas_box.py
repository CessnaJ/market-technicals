import pandas as pd
import numpy as np
from typing import Dict, Any, List


class DarvasBox:
    """
    Nicolas Darvas Box Theory

    3-Day Rule:
    - Top confirmed: After new high, 3 consecutive days don't break it
    - Bottom confirmed: After low point, 3 consecutive days don't break below it

    Box Status:
    - FORMING: Looking for top/bottom
    - ACTIVE: Box confirmed, price inside
    - BROKEN_UP: Price broke above top
    - BROKEN_DOWN: Price broke below bottom
    """

    def __init__(self, lookback_days: int = 52):
        self.lookback_days = lookback_days

    def calculate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate Darvas Boxes

        Args:
            df: Daily OHLCV DataFrame with 'high', 'low', 'close' columns

        Returns:
            Dictionary with box data and all boxes
        """
        if len(df) < 5:
            return {}

        high = df["high"]
        low = df["low"]
        close = df["close"]

        # Initialize tracking arrays
        box_top = pd.Series(index=df.index, dtype=float)
        box_bottom = pd.Series(index=df.index, dtype=float)
        box_status = pd.Series(index=df.index, dtype=object)
        is_new_box = pd.Series(index=df.index, dtype=bool)

        # Track potential tops and bottoms
        potential_top = None
        potential_bottom = None
        top_confirmation_count = 0
        bottom_confirmation_count = 0
        current_status = "FORMING"

        for i in range(len(df)):
            # Check for new high
            if potential_top is None or high.iloc[i] > potential_top:
                potential_top = high.iloc[i]
                top_confirmation_count = 0

            # Check for new low
            if potential_bottom is None or low.iloc[i] < potential_bottom:
                potential_bottom = low.iloc[i]
                bottom_confirmation_count = 0

            # Confirm top (3 days without breaking)
            if potential_top is not None and high.iloc[i] < potential_top:
                top_confirmation_count += 1
            else:
                top_confirmation_count = 0

            # Confirm bottom (3 days without breaking)
            if potential_bottom is not None and low.iloc[i] > potential_bottom:
                bottom_confirmation_count += 1
            else:
                bottom_confirmation_count = 0

            # Update box status
            if top_confirmation_count >= 3 and potential_bottom is not None:
                # Top confirmed, have potential bottom
                box_top.iloc[i] = potential_top
                box_bottom.iloc[i] = potential_bottom
                box_status.iloc[i] = "FORMING"
                current_status = "FORMING"

            elif (
                bottom_confirmation_count >= 3
                and box_top.iloc[i - 1] is not None
            ):
                # Bottom confirmed, box active
                box_top.iloc[i] = box_top.iloc[i - 1]
                box_bottom.iloc[i] = potential_bottom
                box_status.iloc[i] = "ACTIVE"
                current_status = "ACTIVE"

                # Check for box break
                if high.iloc[i] > box_top.iloc[i]:
                    box_status.iloc[i] = "BROKEN_UP"
                    current_status = "BROKEN_UP"
                elif low.iloc[i] < box_bottom.iloc[i]:
                    box_status.iloc[i] = "BROKEN_DOWN"
                    current_status = "BROKEN_DOWN"

            # Track new box formation
            if box_status.iloc[i - 1] in ["BROKEN_UP", "BROKEN_DOWN"]:
                # Previous box broken, looking for new one
                is_new_box = True
            else:
                is_new_box = False

            is_new_box.iloc[i] = is_new_box

        return {
            "box_top": box_top,
            "box_bottom": box_bottom,
            "box_status": box_status,
            "is_new_box": is_new_box,
        }

    def get_all_boxes(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Get all Darvas Boxes for visualization

        Args:
            df: Daily OHLCV DataFrame

        Returns:
            List of box dictionaries
        """
        result = self.calculate(df)

        if not result:
            return []

        box_top = result.get("box_top")
        box_bottom = result.get("box_bottom")
        box_status = result.get("box_status")
        is_new_box = result.get("is_new_box")

        boxes = []
        current_box = None

        for i in range(len(df)):
            status = box_status.iloc[i]

            if status == "FORMING" and is_new_box.iloc[i]:
                # New box forming
                if current_box:
                    current_box["end_date"] = df.index[i - 1]
                    boxes.append(current_box)

                current_box = {
                    "start_date": df.index[i],
                    "end_date": None,
                    "top": box_top.iloc[i],
                    "bottom": box_bottom.iloc[i],
                    "status": "FORMING",
                }

            elif status == "ACTIVE":
                # Box active
                if current_box and current_box["status"] == "ACTIVE":
                    current_box["end_date"] = df.index[i - 1]
                    boxes.append(current_box)
                    current_box = None

                if not current_box:
                    current_box = {
                        "start_date": df.index[i],
                        "end_date": None,
                        "top": box_top.iloc[i],
                        "bottom": box_bottom.iloc[i],
                        "status": "ACTIVE",
                    }

            elif status in ["BROKEN_UP", "BROKEN_DOWN"]:
                # Box broken
                if current_box:
                    current_box["end_date"] = df.index[i - 1]
                    boxes.append(current_box)
                    current_box = None

        # Add last box if still active
        if current_box and box_status.iloc[-1] == "ACTIVE":
            boxes.append(current_box)

        return boxes
