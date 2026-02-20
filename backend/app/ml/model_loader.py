"""
Модуль для загрузки заранее обученной ML-модели и scaler'а.

Модель и scaler загружаются один раз при старте приложения и
переиспользуются в последующих запросах.
"""

import logging
import pickle
from pathlib import Path
from typing import Any, Optional, Tuple


logger = logging.getLogger(__name__)


_MODEL: Optional[Any] = None
_SCALER: Optional[Any] = None


def load_model_and_scaler(model_path: Path, scaler_path: Path) -> Tuple[Any, Any]:
    """
    Загружает модель и scaler с диска и кеширует их в модуле.

    Повторные вызовы будут возвращать уже загруженные объекты.
    """
    global _MODEL, _SCALER

    if _MODEL is not None and _SCALER is not None:
        # Уже загружены — просто возвращаем
        return _MODEL, _SCALER

    if not model_path.exists():
        raise FileNotFoundError(f"Файл модели не найден: {model_path}")
    if not scaler_path.exists():
        raise FileNotFoundError(f"Файл scaler'а не найден: {scaler_path}")

    logger.info("Загружаем модель из %s", model_path)
    with model_path.open("rb") as f:
        _MODEL = pickle.load(f)

    logger.info("Загружаем scaler из %s", scaler_path)
    with scaler_path.open("rb") as f:
        _SCALER = pickle.load(f)

    logger.info("Модель и scaler успешно загружены.")
    return _MODEL, _SCALER


def get_model_and_scaler() -> Tuple[Any, Any]:
    """
    Возвращает уже загруженную модель и scaler.

    Предполагается, что `load_model_and_scaler` был вызван на старте приложения.
    """
    if _MODEL is None or _SCALER is None:
        raise RuntimeError(
            "Модель и/или scaler не загружены. "
            "Убедитесь, что load_model_and_scaler был вызван при старте приложения."
        )

    return _MODEL, _SCALER


