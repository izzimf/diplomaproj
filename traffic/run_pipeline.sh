#!/bin/bash
#
# run_pipeline.sh - Автоматический запуск полного SentinelIoT pipeline
#
# Использование:
#   ./run_pipeline.sh [interface] [capture_time] [backend_url]
#
# Примеры:
#   ./run_pipeline.sh eth1 60
#   ./run_pipeline.sh eth1 120 http://127.0.0.1:8000
#

set -euo pipefail

# Параметры по умолчанию
INTERFACE="${1:-eth1}"
CAPTURE_TIME="${2:-60}"
BACKEND_URL="${3:-http://127.0.0.1:8000}"

# Пути
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")/backend"
CAPTURE_FILE="$SCRIPT_DIR/capture.pcap"
FLOWS_FILE="$SCRIPT_DIR/flows.csv"

echo "=========================================="
echo "Запуск SentinelIoT Pipeline"
echo "Интерфейс: $INTERFACE"
echo "Время захвата: ${CAPTURE_TIME} секунд"
echo "Backend URL: $BACKEND_URL"
echo "=========================================="

# Проверка наличия необходимых скриптов
if [ ! -f "$SCRIPT_DIR/capture.sh" ]; then
    echo "Ошибка: capture.sh не найден в $SCRIPT_DIR"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/run_cicflowmeter.sh" ]; then
    echo "Ошибка: run_cicflowmeter.sh не найден в $SCRIPT_DIR"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/flow_sender.py" ]; then
    echo "Ошибка: flow_sender.py не найден в $SCRIPT_DIR"
    exit 1
fi

# Шаг 1: Захват трафика
echo ""
echo "[1/3] Захват трафика на интерфейсе $INTERFACE..."
if sudo "$SCRIPT_DIR/capture.sh" "$INTERFACE" "$CAPTURE_FILE" "$CAPTURE_TIME"; then
    echo "✓ Захват трафика завершён успешно"
else
    echo "✗ Ошибка при захвате трафика"
    exit 1
fi

# Шаг 2: Конвертация в flows
echo ""
echo "[2/3] Конвертация pcap в flows через CICFlowMeter..."
if "$SCRIPT_DIR/run_cicflowmeter.sh" "$CAPTURE_FILE" "$FLOWS_FILE"; then
    echo "✓ Конвертация завершена успешно"
else
    echo "✗ Ошибка при конвертации"
    exit 1
fi

# Шаг 3: Отправка в ML Backend
echo ""
echo "[3/3] Отправка flows в ML Backend..."

# Проверяем наличие виртуального окружения
if [ -d "$BACKEND_DIR/venv" ]; then
    source "$BACKEND_DIR/venv/bin/activate"
    echo "Активировано виртуальное окружение: $BACKEND_DIR/venv"
elif [ -d "$BACKEND_DIR/.venv" ]; then
    source "$BACKEND_DIR/.venv/bin/activate"
    echo "Активировано виртуальное окружение: $BACKEND_DIR/.venv"
else
    echo "Предупреждение: Виртуальное окружение не найдено, используем системный Python"
fi

if python3 "$SCRIPT_DIR/flow_sender.py" "$FLOWS_FILE" --backend-url "$BACKEND_URL"; then
    echo "✓ Отправка в ML Backend завершена успешно"
else
    echo "✗ Ошибка при отправке в ML Backend"
    exit 1
fi

echo ""
echo "=========================================="
echo "Pipeline завершён успешно!"
echo "=========================================="
echo ""
echo "Файлы:"
echo "  - Захваченный трафик: $CAPTURE_FILE"
echo "  - Flow данные: $FLOWS_FILE"
echo ""

