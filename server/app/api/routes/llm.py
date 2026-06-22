from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep
from app.schemas.llm import LLMConnectionTestRequest, LLMConnectionTestResponse
from app.services.llm import (
    LLMConfigError,
    LLMConnectionTestError,
    test_llm_connection,
)

router = APIRouter()


@router.post(
    "/test-connection",
    response_model=LLMConnectionTestResponse,
    summary="测试大模型服务联通性",
    description="使用 OpenAI 协议兼容配置发送一次极小请求，验证服务是否可用。不保存页面传入的配置。",
)
async def test_connection(
    payload: LLMConnectionTestRequest,
    current_user: CurrentUserDep,
) -> LLMConnectionTestResponse:
    try:
        base_url, model = await test_llm_connection(
            api_key=payload.api_key,
            base_url=payload.base_url,
            model=payload.model,
        )
    except LLMConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except LLMConnectionTestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM 联通测试失败：{exc}",
        ) from exc

    return LLMConnectionTestResponse(
        success=True,
        provider_type=payload.provider_type,
        base_url=base_url,
        model=model,
        message="LLM 服务联通正常",
    )
