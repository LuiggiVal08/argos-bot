"""Integration tests for CorrelationFeatureAnalyzer."""
from __future__ import annotations

import numpy as np
import pytest

from app.infrastructure.training.feature_analyzer_impl import (
    CorrelationFeatureAnalyzer,
    _pearson,
)


@pytest.fixture
def analyzer() -> CorrelationFeatureAnalyzer:
    return CorrelationFeatureAnalyzer()


@pytest.fixture
def sample_data() -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    """200 muestras, 5 features, algunas correlacionadas."""
    np.random.seed(42)
    n = 200
    f1 = np.random.randn(n)                          # ruido
    f2 = np.random.randn(n) * 0.5 + 0.3              # ruido leve
    target_raw = np.random.randn(n)
    f3 = target_raw * 0.8 + np.random.randn(n) * 0.2  # correlacion fuerte
    f4 = -target_raw * 0.6 + np.random.randn(n) * 0.3 # correlacion negativa
    f5 = np.random.randn(n)                          # ruido

    features = np.column_stack([f1, f2, f3, f4, f5])
    # Target: BUY si target_raw > 0.5, SELL si < -0.5, HOLD else
    targets = np.zeros((n, 3))
    for i in range(n):
        if target_raw[i] > 0.5:
            targets[i] = [1, 0, 0]
        elif target_raw[i] < -0.5:
            targets[i] = [0, 1, 0]
        else:
            targets[i] = [0, 0, 1]

    names = ("noise_1", "noise_weak", "strong_bull", "strong_bear", "noise_2")
    return features, targets, names


class TestPearson:
    def test_perfect_positive(self) -> None:
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
        assert abs(_pearson(x, y) - 1.0) < 1e-10

    def test_perfect_negative(self) -> None:
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
        assert abs(_pearson(x, y) - (-1.0)) < 1e-10

    def test_no_correlation(self) -> None:
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([1.0, 1.0, 1.0, 1.0, 1.0])  # std=0
        assert _pearson(x, y) == 0.0


class TestComputeCorrelations:
    def test_returns_dict_with_all_features(
        self, analyzer, sample_data
    ):
        features, targets, names = sample_data
        corrs = await_async(analyzer.compute_correlations(features, targets, names))
        assert set(corrs.keys()) == set(names)
        assert all(isinstance(v, float) for v in corrs.values())

    def test_strong_feature_has_higher_corr(
        self, analyzer, sample_data
    ):
        features, targets, names = sample_data
        corrs = await_async(analyzer.compute_correlations(features, targets, names))
        assert abs(corrs["strong_bull"]) > abs(corrs["noise_1"])
        assert abs(corrs["strong_bear"]) > abs(corrs["noise_1"])

    def test_mismatched_rows_raises(self, analyzer):
        features = np.random.randn(100, 3)
        targets = np.random.randn(50, 3)
        with pytest.raises(Exception):
            await_async(analyzer.compute_correlations(
                features, targets, ("a", "b", "c")
            ))

    def test_mismatched_names_raises(self, analyzer, sample_data):
        features, targets, _ = sample_data
        with pytest.raises(Exception):
            await_async(analyzer.compute_correlations(
                features, targets, ("a", "b")  # solo 2 nombres, pero 5 features
            ))


class TestFilterFeatures:
    def test_filters_noise(
        self, analyzer, sample_data
    ):
        features, targets, names = sample_data
        # Usamos threshold alto para asegurar que el ruido se filtre
        filtered, kept_names = await_async(
            analyzer.filter_features(features, targets, names, min_correlation=0.3)
        )
        # strong_bull y strong_bear tienen correlacion alta (>0.3)
        # noise_1 y noise_2 son ruido y deberian filtrarse (pero depende del random seed)
        assert "strong_bull" in kept_names or "strong_bear" in kept_names
        # Al menos se filtro algo
        assert len(kept_names) < len(names)

    def test_keeps_at_least_three(
        self, analyzer
    ):
        """Si todo es ruido, mantiene las mejores 3."""
        n = 100
        features = np.random.randn(n, 5)
        targets = np.zeros((n, 3))
        targets[:, 2] = 1.0  # todo HOLD (sin correlacion util)
        names = ("a", "b", "c", "d", "e")

        filtered, kept = await_async(
            analyzer.filter_features(features, targets, names, min_correlation=0.5)
        )
        assert len(kept) >= 3
        assert filtered.shape[1] >= 3

    def test_all_pass_if_high_corr(self, analyzer, sample_data):
        features, targets, names = sample_data
        filtered, kept = await_async(
            analyzer.filter_features(features, targets, names, min_correlation=0.0)
        )
        assert len(kept) == len(names)


def await_async(coro):
    """Run an async function synchronously for testing."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        import asyncio
        return asyncio.run_coroutine_threadsafe(coro, loop).result()
    return asyncio.run(coro)
