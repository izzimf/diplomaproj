#!/bin/bash
#
# capture.sh - Скрипт для захвата сетевого трафика с IoT-интерфейса через tcpdump
#
# Использование:
#   ./capture.sh [interface] [output_file] [timeout_seconds]
#
# Примеры:
#   ./capture.sh eth1 capture.pcap 60
#   ./capture.sh eth1 capture.pcap
#   ./capture.sh eth1
#

set -euo pipefail

# Параметры по умолчанию
INTERFACE="${1:-eth1}"
OUTPUT_FILE="${2:-capture.pcap}"
TIMEOUT="${3:-60}"

# Проверка наличия tcpdump
if ! command -v tcpdump &> /dev/null; then
    echo "Ошибка: tcpdump не установлен. Установите: sudo apt-get install tcpdump"
    exit 1
fi

# Проверка прав доступа (tcpdump требует root)
if [ "$EUID" -ne 0 ]; then
    echo "Ошибка: Скрипт должен запускаться с правами root (sudo)"
    exit 1
fi

# Проверка существования интерфейса
if ! ip link show "$INTERFACE" &> /dev/null; then
    echo "Ошибка: Интерфейс $INTERFACE не найден"
    echo "Доступные интерфейсы:"
    ip link show | grep -E "^[0-9]+:" | awk '{print $2}' | sed 's/:$//'
    exit 1
fi

echo "=========================================="
echo "Захват трафика на интерфейсе: $INTERFACE"
echo "Выходной файл: $OUTPUT_FILE"
echo "Таймаут: ${TIMEOUT} секунд"
echo "=========================================="

# Захват трафика через tcpdump
# Опции:
#   -i $INTERFACE     - интерфейс для захвата
#   -w $OUTPUT_FILE   - запись в файл (pcap формат)
#   -n                - не разрешать DNS имена (быстрее)
#   -s 0              - захватывать полные пакеты (snaplen = 0)
#   -c 0              - без ограничения количества пакетов
#   -W 1              - один файл (не ротировать)
#   -G $TIMEOUT       - ротация файла каждые N секунд (но у нас один файл)
#   -U                - писать пакеты сразу (unbuffered)
#   -v                - verbose режим

# Простой вариант с таймаутом через timeout команду
if command -v timeout &> /dev/null; then
    timeout "$TIMEOUT" tcpdump -i "$INTERFACE" -w "$OUTPUT_FILE" -n -s 0 -U -v \
        -c 0 2>&1 | tee capture.log || {
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            echo "Захват завершён по таймауту ($TIMEOUT секунд)"
        else
            echo "Ошибка при захвате трафика (код выхода: $EXIT_CODE)"
            exit $EXIT_CODE
        fi
    }
else
    # Если timeout не доступен, используем tcpdump с ограничением времени через фоновый процесс
    echo "Предупреждение: команда timeout не найдена, используем альтернативный метод"
    tcpdump -i "$INTERFACE" -w "$OUTPUT_FILE" -n -s 0 -U -v -c 0 &
    TCPDUMP_PID=$!
    sleep "$TIMEOUT"
    kill -TERM $TCPDUMP_PID 2>/dev/null || true
    wait $TCPDUMP_PID 2>/dev/null || true
fi

# Проверка результата
if [ -f "$OUTPUT_FILE" ] && [ -s "$OUTPUT_FILE" ]; then
    FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo "=========================================="
    echo "Захват завершён успешно!"
    echo "Файл: $OUTPUT_FILE"
    echo "Размер: $FILE_SIZE"
    echo "=========================================="
else
    echo "Предупреждение: Файл $OUTPUT_FILE пуст или не создан"
    exit 1
fi

