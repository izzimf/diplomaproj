# SentinelIoT — IoT IDS/IPS Pipeline

Полноценная минимальная рабочая система обнаружения и блокировки аномалий в IoT-трафике на базе Machine Learning.

## 🎯 Описание проекта

SentinelIoT — это end-to-end система для мониторинга и защиты IoT устройств от аномального трафика. Система работает на Orange Pi, который выполняет роль Gateway, IDS (Intrusion Detection System) и IPS (Intrusion Prevention System).

### Основные возможности:

- ✅ **Захват сетевого трафика** с IoT устройств через tcpdump
- ✅ **Конвертация в flow-данные** через CICFlowMeter
- ✅ **ML-анализ аномалий** на базе RandomForest
- ✅ **Автоматическая блокировка** подозрительных IP через iptables
- ✅ **Gateway функциональность** (NAT, DHCP, IP forwarding)

---

## 📁 Структура проекта

```
diplomproj/
├── backend/                    # ML Backend (FastAPI)
│   ├── app/
│   │   ├── main.py            # Точка входа FastAPI приложения
│   │   ├── ml/
│   │   │   ├── model_loader.py # Загрузка ML модели и scaler
│   │   │   └── inference.py   # ML инференс
│   │   ├── flows/
│   │   │   └── routes.py      # HTTP API endpoints
│   │   └── utils/
│   │       └── blocker.py    # Блокировка IP через iptables
│   ├── model.pkl              # Обученная RandomForest модель
│   ├── scaler.pkl             # Обученный scaler
│   ├── requirements.txt       # Python зависимости
│   └── README.md              # Документация Backend
│
├── traffic/                    # Traffic Pipeline
│   ├── capture.sh             # Захват трафика через tcpdump
│   ├── run_cicflowmeter.sh    # Конвертация pcap → flows.csv
│   ├── flow_sender.py         # Отправка flows в ML Backend
│   └── run_pipeline.sh        # Автоматический запуск всего pipeline
│
├── NETWORK_SETUP.md           # Инструкция по сетевой настройке
├── SENTINELIOT_SETUP.md       # Полная инструкция по запуску
└── README.md                  # Этот файл
```

---

## 🚀 Быстрый старт

### 1. Предварительные требования

- Orange Pi (или другой Linux SBC) с двумя сетевыми интерфейсами
- Python 3.11+
- Java 8+ (для CICFlowMeter)
- Права root для сетевых операций

### 2. Установка

Следуйте подробным инструкциям в **[SENTINELIOT_SETUP.md](SENTINELIOT_SETUP.md)**

**Краткая версия:**

```bash
# 1. Установка системных зависимостей
sudo apt-get update
sudo apt-get install -y python3.11 python3-pip tcpdump iptables dnsmasq default-jre

# 2. Настройка сети (см. NETWORK_SETUP.md)
sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# 3. Установка Python зависимостей
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Подготовка ML модели
# Скопируйте model.pkl и scaler.pkl в backend/

# 5. Запуск ML Backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 6. Запуск Traffic Pipeline (в другом терминале)
cd traffic
sudo ./run_pipeline.sh eth1 60
```

---

## 📚 Документация

- **[SENTINELIOT_SETUP.md](SENTINELIOT_SETUP.md)** — Полная инструкция по установке и запуску
- **[NETWORK_SETUP.md](NETWORK_SETUP.md)** — Настройка сети (IP forwarding, NAT, DHCP)
- **[backend/README.md](backend/README.md)** — Документация ML Backend

---

## 🔄 End-to-End Pipeline

```
1. IoT Devices генерируют трафик
   ↓
2. Orange Pi (Gateway) перехватывает трафик на eth1
   ↓
3. capture.sh → tcpdump → capture.pcap
   ↓
4. run_cicflowmeter.sh → CICFlowMeter → flows.csv
   ↓
5. flow_sender.py → извлекает 12 признаков → HTTP POST
   ↓
6. ML Backend → inference.py → RandomForest → risk_score
   ↓
7. Если risk_score > 0.61:
   → blocker.py → iptables DROP → IP заблокирован
```

---

## 🛠️ Компоненты системы

### ML Backend (FastAPI)

- **Эндпоинт:** `POST /flows/analyze`
- **Входные данные:** 12 признаков + src_ip
- **Выходные данные:** risk_score, is_anomaly, threshold
- **Порог аномалии:** 0.61
- **Блокировка:** Автоматическая через iptables при обнаружении аномалии

### Traffic Pipeline

- **capture.sh** — Захват трафика через tcpdump
- **run_cicflowmeter.sh** — Конвертация pcap в flows.csv
- **flow_sender.py** — Отправка flows в ML Backend
- **run_pipeline.sh** — Автоматический запуск всего pipeline

---

## 📝 Пример использования

### Тестовый запрос к ML Backend

```bash
curl -X POST "http://127.0.0.1:8000/flows/analyze" \
  -H "Content-Type: application/json" \
  -d '{
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
    "DNS": 0
  }'
```

**Ответ:**

```json
{
  "status": "ok",
  "risk_score": 0.4523,
  "is_anomaly": false,
  "threshold": 0.61,
  "src_ip": "192.168.1.10"
}
```

---

## 🔒 Безопасность

- Блокировка IP выполняется только на Linux системах
- Флаг `ENABLE_BLOCKING` позволяет отключить реальную блокировку для тестирования
- Все действия логируются через стандартный модуль `logging`
- Валидация входных данных через Pydantic

---

## 🐛 Troubleshooting

См. раздел **Troubleshooting** в [SENTINELIOT_SETUP.md](SENTINELIOT_SETUP.md)

---

## 📄 Лицензия

Проект создан в образовательных целях.

---

## 👤 Автор

Senior Backend + Network Engineer

---

## 🔗 Полезные ссылки

- [FastAPI документация](https://fastapi.tiangolo.com/)
- [CICFlowMeter GitHub](https://github.com/ahlashkari/CICFlowMeter)
- [scikit-learn документация](https://scikit-learn.org/)

---

**Готово к использованию!** 🎉

