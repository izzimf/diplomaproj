"""
Модуль для выполнения ML-инференса по IoT flow-данным.
"""

import logging
from typing import Dict, List

import numpy as np
import pandas as pd

from .model_loader import get_model_and_scaler


logger = logging.getLogger(__name__)


# Порог для определения аномалии
ANOMALY_THRESHOLD: float = 0.61


def preprocess_features(feature_dict: Dict[str, float]) -> pd.DataFrame:
    """
    Подготовка входных признаков к подаче в модель:
    - формируем DataFrame в нужном порядке полей;
    - обрабатываем NaN (заполняем нулями);
    - приводим типы к float.
    """
    feature_order: List[str] = [
        "ack_flag_number",
        "HTTPS",
        "Rate",
        "Header_Length",
        "Variance",
        "Max",
        "Tot sum",
        "Time_To_Live",
        "Std",
        "psh_flag_number",
        "Min",
        "DNS",
    ]

    # Создаём DataFrame с одним объектом (одной строкой)
    data = {name: [feature_dict.get(name)] for name in feature_order}
    df = pd.DataFrame(data)

    # Обрабатываем возможные NaN — в проде можно сделать тоньше (импьютация),
    # но для минимально рабочей версии достаточно заполнить нулями.
    df = df.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return df


def predict_risk_score(feature_dict: Dict[str, float]) -> Dict[str, float | bool]:
    """
    Делает полный цикл инференса:
    - препроцессинг;
    - нормализация через scaler;
    - предсказание risk_score моделью;
    - определение is_anomaly.
    """
    model, scaler = get_model_and_scaler()

    # Преобразуем признаки к DataFrame и скейлим
    df = preprocess_features(feature_dict)
    scaled_features = scaler.transform(df.values)

    # Предполагаем, что модель поддерживает predict_proba и бинарную классификацию.
    # В случае, если интерфейс другой, код можно доработать.
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(scaled_features)
        # Берём вероятность "позитивного" класса (обычно индекс 1)
        risk_score = float(proba[0][1])
    elif hasattr(model, "decision_function"):
        # Фолбэк, нормализуем decision_function в [0, 1]
        decision = model.decision_function(scaled_features)
        # Простая сигмоида
        risk_score = float(1 / (1 + np.exp(-decision[0])))
    else:
        # Совсем простой вариант — берём предсказание как есть и зажимаем в [0, 1]
        pred = model.predict(scaled_features)[0]
        risk_score = float(np.clip(pred, 0.0, 1.0))

    is_anomaly = risk_score > ANOMALY_THRESHOLD

    logger.debug(
        "Инференс выполнен. risk_score=%.4f, is_anomaly=%s",
        risk_score,
        is_anomaly,
    )

    return {
        "risk_score": risk_score,
        "is_anomaly": is_anomaly,
    }


