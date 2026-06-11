from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..application.use_cases.build_dataset import (
    BuildDatasetError,
    BuildDatasetUseCase,
)
from ..composition import get_build_dataset_usecase
from ..domain.value_objects.model_config import ModelConfig
from ..domain.value_objects.scaler_type import ScalerType

router = APIRouter(prefix="/dataset", tags=["dataset"])


@router.post(
    "/build",
    summary="Build a training dataset from symbol parquet files.",
)
async def build_dataset(
    request: Request,
    symbols: list[str],
    config: ModelConfig | None = None,
    scaler: str = "standard",
    use_atr_labeling: bool = True,
) -> dict:
    use_case: BuildDatasetUseCase = get_build_dataset_usecase(request)
    try:
        symbol_files: dict[str, Path] = {}
        for sym in symbols:
            path = Path(f"data/datasets/{sym.lower().replace('/', '_')}.parquet")
            if not path.exists():
                raise HTTPException(404, f"parquet not found for {sym}")
            symbol_files[sym] = path

        scaler_type = ScalerType(scaler)
        result = await use_case.execute(
            symbol_files=symbol_files,
            config=config,
            scaler_type=scaler_type,
            use_atr_labeling=use_atr_labeling,
        )
        return {
            "dataset_id": result.dataset_id,
            "n_samples": result.n_samples,
            "n_features": result.n_features,
            "window_shape": list(result.window_shape),
            "class_counts": result.class_counts,
            "feature_names": list(result.feature_names),
        }
    except BuildDatasetError as e:
        raise HTTPException(422, str(e)) from e
