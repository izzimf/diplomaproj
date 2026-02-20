
### Архитектура (вкратце)

- `app/main.py` — точка входа FastAPI:
  - на событие `startup` один раз загружает `model.pkl` и `scaler.pkl`;
  - подключает роутер `flows/routes.py` по префиксу `/flows`.
- `app/flows/routes.py`:
  - описывает POST-эндпоинт `POST /flows/analyze`;
  - валидирует входные данные через Pydantic;
  - вызывает ML-инференс;
  - при `risk_score > 0.61` логирует аномалию и вызывает блокировку IP.
- `app/ml/model_loader.py`:
  - загружает и кеширует модель и scaler (однократно).
- `app/ml/inference.py`:
  - готовит признаки в `pandas.DataFrame`;
  - обрабатывает NaN/inf;
  - прогоняет через scaler и модель;
  - считает `risk_score` и `is_anomaly` (порог `0.61`).
- `app/utils/blocker.py`:
  - блокирует IP через `iptables` на Linux (если `ENABLE_BLOCKING=True`);
  - на других ОС или при `ENABLE_BLOCKING=False` только логирует.

---

### Подготовка окружения

Из корня проекта:

```bash
cd backend
pip install -r requirements.txt
```

Убедитесь, что в директории `backend/` лежат файлы:

- `model.pkl` — сериализованная модель scikit-learn (например, RandomForestClassifier);
- `scaler.pkl` — сериализованный scaler (например, StandardScaler), которым данные преобразовывались при обучении.

---

### Запуск сервера

Находясь в директории `backend`:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

После запуска:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`

---

### API: Анализ одного flow

**Эндпоинт**

- Метод: `POST`
- URL: `/flows/analyze`
- Описание: Принимает одну flow-запись (12 признаков + IP источника), возвращает:
  - `risk_score` ∈ [0, 1];
  - `is_anomaly` (bool);
  - `threshold` (порог, по умолчанию `0.61`);
  - `src_ip`.

**Тело запроса (JSON)**

```json
{
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
}
```

Обратите внимание: поле с пробелом обозначается как `"Tot sum"` в JSON, но внутри кода маппится на поле `Tot_sum`.

**Пример запроса (cURL)**

```bash
curl -X POST "http://localhost:8000/flows/analyze" \
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

**Пример ответа**

```json
{
  "status": "ok",
  "risk_score": 0.78,
  "is_anomaly": true,
  "threshold": 0.61,
  "src_ip": "192.168.1.10"
}
```

Если `risk_score > 0.61`, в логах появится предупреждение и будет вызвана функция блокировки IP.

---

### Блокировка IP (iptables)

- За блокировку отвечает модуль `app/utils/blocker.py`.
- Глобальный флаг:

```python
ENABLE_BLOCKING: Final[bool] = True
```

- Рекомендации:
  - В **prod на Linux** можно оставить `True`, чтобы реально блокировать IP.
  - В **dev/на macOS/Windows** целесообразно установить `ENABLE_BLOCKING = False`, чтобы команда `iptables` не вызывалась.

При включённой блокировке и наличии аномалии отправляется команда:

```bash
sudo iptables -A INPUT -s <IP> -j DROP
```

Все действия (успехи/ошибки блокировки) логируются через стандартный модуль `logging`.


