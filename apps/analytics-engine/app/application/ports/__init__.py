"""Application ports (Protocol classes for adapter contracts).

Each port abstracts an I/O concern that the use cases need but must
not couple to. The infrastructure layer provides the concrete
adapters (CCXT, TA, broker, Keras).
"""
from .atr_calculator import AtrCalculator, AtrCalculatorError
from .backtest_reporter import BacktestReporter, MetricsCalculator
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
from .execution_logger import ExecutionLogger
from .feature_analyzer import AnalysisError, FeatureAnalyzer
from .incident_reporter import IncidentReporter
from .incident_repository import IncidentRepository
from .min_lot_provider import MarketConstraints, MinLotProvider, MinLotProviderError
from .model_predictor import ModelPredictor, PredictionError
from .model_trainer import ModelTrainer, TrainingError
from .ohlcv_source import OhlcvSource, OhlcvSourceError
from .signal_consumer import PositionRepository, SignalConsumer
from .strategy import Strategy, StrategyRegistry

__all__ = [
    "AnalysisError",
    "AtrCalculator",
    "AtrCalculatorError",
    "BacktestReporter",
    "BalanceProvider",
    "BalanceProviderError",
    "CheckpointIOError",
    "CheckpointNotFoundError",
    "CheckpointRepository",
    "DataPreprocessor",
    "ExecutionLogger",
    "FeatureAnalyzer",
    "IncidentReporter",
    "IncidentRepository",
    "InsufficientDataError",
    "MarketConstraints",
    "MetricsCalculator",
    "MinLotProvider",
    "MinLotProviderError",
    "ModelPredictor",
    "ModelTrainer",
    "OhlcvSource",
    "OhlcvSourceError",
    "PositionRepository",
    "PredictionError",
    "PreprocessingError",
    "SignalConsumer",
    "Strategy",
    "StrategyRegistry",
    "TrainingError",
]
