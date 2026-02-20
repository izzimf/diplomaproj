import logging
from pathlib import Path

from fastapi import FastAPI

from .flows.routes import router as flows_router
from .ml.model_loader import load_model_and_scaler


# Базовая конфигурация логирования для всего приложения
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Путь к директории backend
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "model.pkl"
SCALER_PATH = BASE_DIR / "scaler.pkl"


def create_app() -> FastAPI:
    """
    Фабрика приложения FastAPI.
    """
    fastapi_app = FastAPI(
        title="IoT Traffic Anomaly Detection API",
        description="Минимальная система обнаружения аномалий IoT-трафика на базе RandomForest.",
        version="1.0.0",
    )

    # Подключаем роутер с namespace /flows
    fastapi_app.include_router(flows_router, prefix="/flows", tags=["flows"])

    @fastapi_app.on_event("startup")
    async def on_startup() -> None:
        """
        Стартап-хук: загружаем модель и scaler один раз при старте приложения.
        """
        logger.info("Приложение стартует, загружаем ML модель и scaler...")
        load_model_and_scaler(model_path=MODEL_PATH, scaler_path=SCALER_PATH)
        logger.info("ML модель и scaler успешно загружены.")

    return fastapi_app


app = create_app()


