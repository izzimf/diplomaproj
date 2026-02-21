#!/usr/bin/env python3
"""
flow_sender.py - Скрипт для чтения flows.csv и отправки данных в ML Backend через HTTP.

Скрипт:
1. Читает flows.csv через pandas
2. Извлекает 12 нужных признаков
3. Обрабатывает NaN значения
4. Формирует JSON для каждого flow
5. Отправляет POST запрос на http://127.0.0.1:8000/flows/analyze
6. Логирует ответы и обрабатывает ошибки

Использование:
    python flow_sender.py [flows.csv] [backend_url]

Примеры:
    python flow_sender.py flows.csv
    python flow_sender.py flows.csv http://127.0.0.1:8000
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


# 12 признаков, которые нужны для ML модели
REQUIRED_FEATURES: List[str] = [
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


def read_flows_csv(csv_path: Path) -> pd.DataFrame:
    """
    Читает CSV файл с flow-данными через pandas.

    Обрабатывает возможные проблемы с кодировкой и разделителями.
    """
    logger.info("Читаем CSV файл: %s", csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"Файл не найден: {csv_path}")

    # Пробуем разные варианты чтения CSV
    try:
        df = pd.read_csv(csv_path, encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning("Ошибка кодировки UTF-8, пробуем latin-1")
        df = pd.read_csv(csv_path, encoding="latin-1")
    except Exception as exc:
        logger.error("Ошибка при чтении CSV: %s", exc)
        raise

    logger.info("Прочитано строк: %d, колонок: %d", len(df), len(df.columns))
    return df


def extract_features(row: pd.Series, src_ip_column: str = "Src IP") -> Optional[Dict]:
    """
    Извлекает нужные 12 признаков из строки DataFrame.

    Обрабатывает NaN значения (заменяет на 0.0).
    Возвращает словарь с признаками и src_ip, или None если данные некорректны.
    """
    # Извлекаем IP источника
    if src_ip_column not in row.index:
        # Пробуем альтернативные названия колонок
        for alt_name in ["Source IP", "src_ip", "SourceIP", "SrcIP"]:
            if alt_name in row.index:
                src_ip_column = alt_name
                break
        else:
            logger.warning("Колонка с IP источника не найдена. Доступные колонки: %s", list(row.index))
            return None

    src_ip = str(row[src_ip_column]).strip()
    if not src_ip or src_ip == "nan" or src_ip == "None":
        logger.warning("IP источника пустой или некорректный: %s", src_ip)
        return None

    # Формируем словарь признаков
    features: Dict[str, float] = {}

    for feature_name in REQUIRED_FEATURES:
        # Пробуем найти колонку с точным совпадением
        if feature_name in row.index:
            value = row[feature_name]
        else:
            # Пробуем найти колонку с похожим названием (case-insensitive)
            matching_cols = [col for col in row.index if col.lower() == feature_name.lower()]
            if matching_cols:
                value = row[matching_cols[0]]
            else:
                logger.warning("Признак '%s' не найден в строке. Доступные: %s", feature_name, list(row.index))
                value = 0.0

        # Обработка NaN, inf, -inf
        if pd.isna(value) or value == np.inf or value == -np.inf:
            features[feature_name] = 0.0
        else:
            try:
                features[feature_name] = float(value)
            except (ValueError, TypeError):
                logger.warning("Не удалось преобразовать '%s' в float: %s", feature_name, value)
                features[feature_name] = 0.0

    features["src_ip"] = src_ip
    return features


def send_flow_to_backend(features: Dict, backend_url: str, timeout: int = 10) -> Optional[Dict]:
    """
    Отправляет flow-данные в ML Backend через HTTP POST.

    Возвращает ответ от сервера (dict) или None при ошибке.
    """
    # Формируем JSON payload
    payload = {
        "src_ip": features["src_ip"],
        **{k: v for k, v in features.items() if k != "src_ip"},
    }

    url = f"{backend_url}/flows/analyze"

    try:
        logger.debug("Отправляем запрос на %s с данными: %s", url, payload)
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()  # Вызовет исключение при HTTP ошибке

        result = response.json()
        logger.info(
            "Ответ от backend: IP=%s, risk_score=%.4f, is_anomaly=%s",
            result.get("src_ip"),
            result.get("risk_score"),
            result.get("is_anomaly"),
        )

        return result

    except requests.exceptions.Timeout:
        logger.error("Таймаут при отправке запроса на %s", url)
        return None
    except requests.exceptions.ConnectionError:
        logger.error("Ошибка подключения к %s. Убедитесь, что backend запущен.", url)
        return None
    except requests.exceptions.HTTPError as exc:
        logger.error("HTTP ошибка %d: %s", exc.response.status_code, exc.response.text)
        return None
    except requests.exceptions.RequestException as exc:
        logger.error("Ошибка при отправке запроса: %s", exc)
        return None
    except Exception as exc:
        logger.exception("Неожиданная ошибка: %s", exc)
        return None


def main():
    """Главная функция скрипта."""
    parser = argparse.ArgumentParser(
        description="Отправка flow-данных из CSV в ML Backend для анализа аномалий"
    )
    parser.add_argument(
        "csv_file",
        nargs="?",
        default="flows.csv",
        help="Путь к CSV файлу с flow-данными (по умолчанию: flows.csv)",
    )
    parser.add_argument(
        "--backend-url",
        default="http://127.0.0.1:8000",
        help="URL ML Backend API (по умолчанию: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Таймаут HTTP запросов в секундах (по умолчанию: 10)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Ограничить количество обрабатываемых flow (для тестирования)",
    )

    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    backend_url = args.backend_url.rstrip("/")

    logger.info("==========================================")
    logger.info("Запуск flow_sender.py")
    logger.info("CSV файл: %s", csv_path)
    logger.info("Backend URL: %s", backend_url)
    logger.info("==========================================")

    # Читаем CSV
    try:
        df = read_flows_csv(csv_path)
    except Exception as exc:
        logger.error("Ошибка при чтении CSV: %s", exc)
        sys.exit(1)

    # Ограничиваем количество строк, если указан --limit
    if args.limit:
        df = df.head(args.limit)
        logger.info("Ограничено до %d строк для тестирования", args.limit)

    # Обрабатываем каждую строку
    total_rows = len(df)
    success_count = 0
    error_count = 0
    anomaly_count = 0

    logger.info("Начинаем обработку %d flow-записей...", total_rows)

    for idx, row in df.iterrows():
        logger.debug("Обрабатываем строку %d/%d", idx + 1, total_rows)

        # Извлекаем признаки
        features = extract_features(row)
        if features is None:
            error_count += 1
            continue

        # Отправляем в backend
        result = send_flow_to_backend(features, backend_url, timeout=args.timeout)
        if result is None:
            error_count += 1
            continue

        success_count += 1
        if result.get("is_anomaly"):
            anomaly_count += 1
            logger.warning(
                "⚠️  АНОМАЛИЯ обнаружена! IP=%s, risk_score=%.4f",
                result.get("src_ip"),
                result.get("risk_score"),
            )

    # Итоговая статистика
    logger.info("==========================================")
    logger.info("Обработка завершена")
    logger.info("Всего flow: %d", total_rows)
    logger.info("Успешно обработано: %d", success_count)
    logger.info("Ошибок: %d", error_count)
    logger.info("Аномалий обнаружено: %d", anomaly_count)
    logger.info("==========================================")

    # Возвращаем код выхода в зависимости от результата
    if error_count == total_rows:
        logger.error("Все запросы завершились ошибкой!")
        sys.exit(1)
    elif error_count > 0:
        logger.warning("Некоторые запросы завершились ошибкой")
        sys.exit(0)  # Частичный успех
    else:
        sys.exit(0)  # Полный успех


if __name__ == "__main__":
    main()

