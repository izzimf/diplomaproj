#!/bin/bash
#
# run_cicflowmeter.sh - Скрипт для запуска CICFlowMeter и конвертации pcap в flows.csv
#
# Требования:
#   - Установленный CICFlowMeter (Java приложение)
#   - Java Runtime Environment (JRE) версии 8 или выше
#
# Использование:
#   ./run_cicflowmeter.sh [input_pcap] [output_csv]
#
# Примеры:
#   ./run_cicflowmeter.sh capture.pcap flows.csv
#   ./run_cicflowmeter.sh capture.pcap
#   ./run_cicflowmeter.sh
#

set -euo pipefail

# Параметры по умолчанию
INPUT_PCAP="${1:-capture.pcap}"
OUTPUT_CSV="${2:-flows.csv}"

# Путь к CICFlowMeter (измените на ваш путь)
# Обычно CICFlowMeter находится в /opt/CICFlowMeter или в домашней директории
CICFLOWMETER_DIR="${CICFLOWMETER_DIR:-/opt/CICFlowMeter}"
CICFLOWMETER_JAR="${CICFLOWMETER_JAR:-$CICFLOWMETER_DIR/CICFlowMeter.jar}"

# Проверка наличия Java
if ! command -v java &> /dev/null; then
    echo "Ошибка: Java не установлена. Установите: sudo apt-get install default-jre"
    exit 1
fi

# Проверка версии Java (нужна версия 8+)
JAVA_VERSION=$(java -version 2>&1 | head -n 1 | cut -d'"' -f2 | sed '/^1\./s///' | cut -d'.' -f1)
if [ "$JAVA_VERSION" -lt 8 ]; then
    echo "Ошибка: Требуется Java версии 8 или выше. Текущая версия: $JAVA_VERSION"
    exit 1
fi

# Проверка существования входного файла
if [ ! -f "$INPUT_PCAP" ]; then
    echo "Ошибка: Входной файл $INPUT_PCAP не найден"
    exit 1
fi

# Проверка существования CICFlowMeter JAR
if [ ! -f "$CICFLOWMETER_JAR" ]; then
    echo "Ошибка: CICFlowMeter JAR не найден: $CICFLOWMETER_JAR"
    echo ""
    echo "Инструкция по установке CICFlowMeter:"
    echo "1. Скачайте CICFlowMeter с https://github.com/ahlashkari/CICFlowMeter"
    echo "2. Распакуйте архив"
    echo "3. Установите переменную окружения: export CICFLOWMETER_DIR=/path/to/CICFlowMeter"
    echo "   или укажите путь к JAR файлу: export CICFLOWMETER_JAR=/path/to/CICFlowMeter.jar"
    exit 1
fi

echo "=========================================="
echo "Запуск CICFlowMeter"
echo "Входной файл: $INPUT_PCAP"
echo "Выходной файл: $OUTPUT_CSV"
echo "CICFlowMeter JAR: $CICFLOWMETER_JAR"
echo "=========================================="

# Создаём временную директорию для выходных файлов CICFlowMeter
TEMP_OUTPUT_DIR=$(mktemp -d)
trap "rm -rf $TEMP_OUTPUT_DIR" EXIT

# Запуск CICFlowMeter
# CICFlowMeter обычно принимает параметры:
#   -i <input_pcap> - входной pcap файл
#   -o <output_dir> - выходная директория для CSV файлов
#
# Примечание: Точные параметры могут отличаться в зависимости от версии CICFlowMeter.
# Проверьте документацию вашей версии.

echo "Запуск CICFlowMeter..."
cd "$(dirname "$CICFLOWMETER_JAR")"

# Попытка запуска с разными вариантами параметров (в зависимости от версии CICFlowMeter)
if java -jar "$CICFLOWMETER_JAR" -i "$(realpath "$INPUT_PCAP")" -o "$TEMP_OUTPUT_DIR" 2>&1 | tee cicflowmeter.log; then
    echo "CICFlowMeter завершился успешно"
elif java -jar "$CICFLOWMETER_JAR" "$(realpath "$INPUT_PCAP")" "$TEMP_OUTPUT_DIR" 2>&1 | tee cicflowmeter.log; then
    echo "CICFlowMeter завершился успешно (альтернативный формат параметров)"
else
    echo "Ошибка: CICFlowMeter завершился с ошибкой. Проверьте логи в cicflowmeter.log"
    exit 1
fi

# Поиск созданного CSV файла в выходной директории
# CICFlowMeter обычно создаёт файлы с именами типа: <timestamp>_Flow.csv или просто Flow.csv
FOUND_CSV=$(find "$TEMP_OUTPUT_DIR" -name "*.csv" -type f | head -n 1)

if [ -z "$FOUND_CSV" ]; then
    echo "Ошибка: CICFlowMeter не создал CSV файл в директории $TEMP_OUTPUT_DIR"
    echo "Содержимое директории:"
    ls -la "$TEMP_OUTPUT_DIR"
    exit 1
fi

# Копируем найденный CSV файл в указанное место
cp "$FOUND_CSV" "$OUTPUT_CSV"

# Проверка результата
if [ -f "$OUTPUT_CSV" ] && [ -s "$OUTPUT_CSV" ]; then
    FILE_SIZE=$(du -h "$OUTPUT_CSV" | cut -f1)
    LINE_COUNT=$(wc -l < "$OUTPUT_CSV")
    echo "=========================================="
    echo "Конвертация завершена успешно!"
    echo "Файл: $OUTPUT_CSV"
    echo "Размер: $FILE_SIZE"
    echo "Количество строк: $LINE_COUNT"
    echo "=========================================="
else
    echo "Ошибка: Файл $OUTPUT_CSV пуст или не создан"
    exit 1
fi

