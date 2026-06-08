"""Application ports (Protocol classes for adapter contracts).

Each port abstracts an I/O concern that the use cases need but must
not couple to. The infrastructure layer provides the concrete
adapters (CCXT, TA, broker, Keras).
"""
from .atr_calculator import AtrCalculator, AtrCalculatorError
from .balance_provider import BalanceProvider, BalanceProviderError
from .checkpoint_repository import (
    CheckpointIOError,
    CheckpointNotFoundError,
    CheckpointRepository,
)
from .data_preprocessor import (
    DataPreprocessor,
    InsufficientDataError,
    PreprocessingError,
)
from .feature_analyzer import AnalysisError, FeatureAnalyzer
from .incident_reporter import IncidentReporter
from .incident_repository import IncidentRepository
from .min_lot_provider import MarketConstraints, MinLotProvider, MinLotProviderError
from .model_predictor import ModelPredictor, PredictionError
from .model_trainer import ModelTrainer, TrainingError
from .ohlcv_source import OhlcvSource, OhlcvSourceError

__all__ = [
    "AnalysisError",
    "AtrCalculator",
    "AtrCalculatorError",
    "BalanceProvider",
    "BalanceProviderError",
    "CheckpointIOError",
    "CheckpointNotFoundError",
    "CheckpointRepository",
    "DataPreprocessor",
    "FeatureAnalyzer",
    "IncidentReporter",
    "IncidentRepository",
    "InsufficientDataError",
    "MarketConstraints",
    "MinLotProvider",
    "MinLotProviderError",
    "ModelPredictor",
    "ModelTrainer",
    "OhlcvSource",
    "OhlcvSourceError",
    "PredictionError",
    "PreprocessingError",
    "TrainingError",
]
