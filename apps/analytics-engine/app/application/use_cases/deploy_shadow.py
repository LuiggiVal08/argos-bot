from __future__ import annotations

from dataclasses import dataclass

from ...domain.entities.shadow_model import ShadowDeployment, ShadowModelManager


@dataclass(frozen=True)
class DeployShadowResult:
    success: bool
    deployment: ShadowDeployment | None
    message: str


class DeployShadowUseCase:
    def __init__(self, manager: ShadowModelManager) -> None:
        self._manager = manager

    async def execute(self, model_id: str, version: str) -> DeployShadowResult:
        try:
            deployment = self._manager.deploy(model_id, version)
            return DeployShadowResult(
                success=True,
                deployment=deployment,
                message=f"shadow {model_id} v{version} deployed",
            )
        except RuntimeError as e:
            return DeployShadowResult(
                success=False,
                deployment=None,
                message=str(e),
            )


class ListShadowsUseCase:
    def __init__(self, manager: ShadowModelManager) -> None:
        self._manager = manager

    async def execute(self) -> list[ShadowDeployment]:
        return self._manager.list_all()
