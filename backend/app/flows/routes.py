"""
Маршруты для работы с IoT flow-данными.
"""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, Field, IPvAnyAddress

from ..ml.inference import ANOMALY_THRESHOLD, predict_risk_score
from ..utils.blocker import block_ip


logger = logging.getLogger(__name__)


router = APIRouter()


class FlowFeatures(BaseModel):
    """
    Pydantic-модель для валидации входных признаков flow-записи.
    """

    # IP-адрес источника (для блокировки при необходимости)
    src_ip: IPvAnyAddress = Field(..., description="IP-адрес источника трафика")

    ack_flag_number: float = Field(..., description="ACK флаг")
    HTTPS: float = Field(..., description="HTTPS признак")
    Rate: float = Field(..., description="Скорость потока")
    Header_Length: float = Field(..., description="Длина заголовка")
    Variance: float = Field(..., description="Дисперсия признаков")
    Max: float = Field(..., description="Максимальное значение")
    Tot_sum: float = Field(..., alias="Tot sum", description="Суммарное значение")
    Time_To_Live: float = Field(..., description="TTL")
    Std: float = Field(..., description="Стандартное отклонение")
    psh_flag_number: float = Field(..., description="PSH флаг")
    Min: float = Field(..., description="Минимальное значение")
    DNS: float = Field(..., description="DNS признак")

    class Config:
        # Позволяем использовать ключ "Tot sum" в JSON, маппим на поле Tot_sum
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "src_ip": "192.168.1.10",
                "ack_flag_number": 1,
                "HTTPS": 0,
                "Rate": 123.45,
                "Header_Length": 20,
                "Variance": 0.12,
                "Max": 10.0,
                "Tot sum": 100.0,
                "Time_To_Live": 64,
                "Std": 0.35,
                "psh_flag_number": 0,
                "Min": 1.0,
                "DNS": 0,
            }
        }


class AnalyzeResponse(BaseModel):
    """
    Структура ответа API.
    """

    status: Literal["ok"] = Field(default="ok", description="Статус ответа")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Риск аномалии (0-1)")
    is_anomaly: bool = Field(..., description="Флаг аномальности")
    threshold: float = Field(..., description="Пороговое значение для аномалии")
    src_ip: str = Field(..., description="IP-адрес источника")


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Анализ IoT flow-данных на аномалии",
)
async def analyze_flow(
    payload: Annotated[
        FlowFeatures,
        Body(
            ...,
            description="Признаки одной flow-записи, включая IP источника.",
        ),
    ],
) -> AnalyzeResponse:
    """
    Принимает flow-данные, делает ML-инференс и, при необходимости, блокирует IP.
    """
    try:
        # Преобразуем в dict с учётом alias ("Tot sum")
        feature_dict = payload.model_dump(by_alias=True)
        src_ip = str(feature_dict.pop("src_ip"))

        # Инференс
        result = predict_risk_score(feature_dict)
        risk_score = float(result["risk_score"])
        is_anomaly = bool(result["is_anomaly"])

        # Логируем и блокируем IP при превышении порога
        if is_anomaly:
            logger.warning(
                "Обнаружена аномалия. IP=%s, risk_score=%.4f (> %.2f)",
                src_ip,
                risk_score,
                ANOMALY_THRESHOLD,
            )
            block_ip(src_ip)
        else:
            logger.info(
                "Трафик нормальный. IP=%s, risk_score=%.4f (<= %.2f)",
                src_ip,
                risk_score,
                ANOMALY_THRESHOLD,
            )

        return AnalyzeResponse(
            risk_score=risk_score,
            is_anomaly=is_anomaly,
            threshold=ANOMALY_THRESHOLD,
            src_ip=src_ip,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ошибка при анализе flow-данных: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during flow analysis.",
        ) from exc


