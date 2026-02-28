from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd


class BaseIndicator(ABC):
    """
    Abstract base class for all indicators

    All indicator classes should inherit from this and implement
    the calculate method.
    """

    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate the indicator

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary with calculated indicator values
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of this indicator"""
        pass

    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Return the parameters used for this indicator"""
        pass
