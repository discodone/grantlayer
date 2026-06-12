"""Health and readiness endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ...core.runtime_config import describe_runtime_config
from ..schemas import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, response_model_by_alias=True)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="grantlayer",
        checkType="liveness",
    )


@router.get(
    "/readiness",
    responses={503: {"model": ReadinessResponse}},
)
def readiness():
    try:
        runtime_info = describe_runtime_config()
        return ReadinessResponse(
            status="ready",
            service="grantlayer",
            checkType="readiness",
            runtimeMode=runtime_info.get("runtimeMode"),
            isProductionLike=runtime_info.get("isProductionLike"),
        )
    except ValueError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": "grantlayer",
                "checkType": "readiness",
                "errorCode": "RUNTIME_CONFIG_INVALID",
            },
        )
