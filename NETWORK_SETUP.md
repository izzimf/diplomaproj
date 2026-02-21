# Сетевая настройка Orange Pi для SentinelIoT

Данный документ описывает настройку Orange Pi в качестве Gateway + IDS/IPS для IoT устройств.

## Архитектура сети

```
IoT Devices (192.168.1.0/24)
    ↓
Orange Pi (Gateway)
    ├── eth0 (WAN) → Router → Internet
    └── eth1 (LAN) → IoT Devices
    ↓
Router
    ↓
Internet
```

## Предварительные требования

- Orange Pi с установленным Linux (Debian/Ubuntu)
- Два сетевых интерфейса:
  - `eth0` (или `wlan0`) — подключение к роутеру/интернету (WAN)
  - `eth1` (или другой) — подключение к IoT устройствам (LAN)
- Права root для настройки сети и iptables

---

## 1. Включение IP Forwarding

IP Forwarding позволяет Orange Pi маршрутизировать пакеты между интерфейсами.

### Временное включение (до перезагрузки):

```bash
sudo sysctl -w net.ipv4.ip_forward=1
```

### Постоянное включение:

```bash
# Редактируем /etc/sysctl.conf
sudo nano /etc/sysctl.conf

# Раскомментируем или добавьте строку:
net.ipv4.ip_forward=1

# Применяем изменения
sudo sysctl -p
```

### Проверка:

```bash
cat /proc/sys/net/ipv4/ip_forward
# Должно вывести: 1
```

---

## 2. Настройка сетевых интерфейсов

### 2.1. Настройка WAN интерфейса (eth0)

Обычно получает IP через DHCP от роутера:

```bash
# Редактируем /etc/network/interfaces или используем netplan/systemd-networkd
sudo nano /etc/network/interfaces
```

Пример для статического IP (если нужно):

```
auto eth0
iface eth0 inet dhcp
    # или статический:
    # address 192.168.0.100
    # netmask 255.255.255.0
    # gateway 192.168.0.1
```

### 2.2. Настройка LAN интерфейса (eth1) для IoT устройств

```bash
sudo nano /etc/network/interfaces
```

Добавьте:

```
auto eth1
iface eth1 inet static
    address 192.168.1.1
    netmask 255.255.255.0
    network 192.168.1.0
    broadcast 192.168.1.255
```

Примените изменения:

```bash
sudo ifdown eth1 && sudo ifup eth1
# или
sudo systemctl restart networking
```

---

## 3. Настройка NAT через iptables

NAT (Network Address Translation) позволяет IoT устройствам выходить в интернет через Orange Pi.

### 3.1. Базовые правила NAT

```bash
# Очистка существующих правил (ОСТОРОЖНО: очистит все правила!)
sudo iptables -t nat -F
sudo iptables -F

# Включаем NAT для исходящего трафика с LAN (eth1) на WAN (eth0)
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# Разрешаем форвардинг пакетов между интерфейсами
sudo iptables -A FORWARD -i eth1 -o eth0 -j ACCEPT
sudo iptables -A FORWARD -i eth0 -o eth1 -m state --state RELATED,ESTABLISHED -j ACCEPT
```

### 3.2. Сохранение правил iptables

Для Debian/Ubuntu:

```bash
# Установка утилиты для сохранения правил
sudo apt-get install iptables-persistent

# Сохранение текущих правил
sudo netfilter-persistent save
# или
sudo iptables-save > /etc/iptables/rules.v4
```

Для систем с systemd:

```bash
# Создаём сервис для загрузки правил при загрузке
sudo nano /etc/systemd/system/iptables-restore.service
```

Содержимое:

```ini
[Unit]
Description=Restore iptables rules
Before=network-pre.target

[Service]
Type=oneshot
ExecStart=/sbin/iptables-restore /etc/iptables/rules.v4
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Активируем:

```bash
sudo systemctl enable iptables-restore.service
```

---

## 4. Настройка FORWARD правил для безопасности

Дополнительные правила для контроля трафика:

```bash
# Разрешаем только исходящий трафик от IoT устройств
sudo iptables -A FORWARD -i eth1 -o eth0 -s 192.168.1.0/24 -j ACCEPT

# Разрешаем ответный трафик
sudo iptables -A FORWARD -i eth0 -o eth1 -d 192.168.1.0/24 -m state --state RELATED,ESTABLISHED -j ACCEPT

# Блокируем прямой доступ из интернета к IoT устройствам (по умолчанию)
sudo iptables -A FORWARD -i eth0 -o eth1 -j DROP

# Логируем заблокированные пакеты (опционально)
sudo iptables -A FORWARD -i eth0 -o eth1 -j LOG --log-prefix "BLOCKED-FORWARD: "
```

---

## 5. Настройка DHCP через dnsmasq

dnsmasq предоставляет DHCP и DNS сервисы для IoT устройств.

### 5.1. Установка dnsmasq

```bash
sudo apt-get update
sudo apt-get install dnsmasq
```

### 5.2. Конфигурация dnsmasq

```bash
# Резервная копия оригинального конфига
sudo cp /etc/dnsmasq.conf /etc/dnsmasq.conf.backup

# Редактируем конфиг
sudo nano /etc/dnsmasq.conf
```

Добавьте или измените следующие строки:

```
# Интерфейс для прослушивания
interface=eth1

# Диапазон IP адресов для DHCP
dhcp-range=192.168.1.100,192.168.1.200,255.255.255.0,12h

# Шлюз по умолчанию (Orange Pi)
dhcp-option=3,192.168.1.1

# DNS серверы (можно использовать публичные DNS)
dhcp-option=6,8.8.8.8,8.8.4.4

# Логирование
log-queries
log-dhcp

# Не использовать /etc/resolv.conf для DNS (используем внешние DNS)
no-resolv

# Внешние DNS серверы
server=8.8.8.8
server=8.8.4.4
```

### 5.3. Запуск и автозапуск dnsmasq

```bash
# Перезапуск dnsmasq
sudo systemctl restart dnsmasq

# Включение автозапуска
sudo systemctl enable dnsmasq

# Проверка статуса
sudo systemctl status dnsmasq
```

### 5.4. Проверка DHCP

```bash
# Просмотр логов
sudo tail -f /var/log/syslog | grep dnsmasq

# Просмотр арендованных IP
cat /var/lib/dnsmasq/dnsmasq.leases
```

---

## 6. Настройка Orange Pi как Default Gateway для IoT устройств

После настройки DHCP, IoT устройства автоматически получат Orange Pi (192.168.1.1) как default gateway через опцию DHCP `dhcp-option=3,192.168.1.1`.

### Для устройств со статической конфигурацией:

Настройте на IoT устройстве:
- **Gateway (шлюз)**: `192.168.1.1`
- **IP адрес**: `192.168.1.x` (где x от 2 до 99 или 201-254, избегая диапазона DHCP)
- **Subnet mask**: `255.255.255.0`
- **DNS**: `192.168.1.1` (или `8.8.8.8`)

---

## 7. Проверка настройки

### 7.1. Проверка IP forwarding

```bash
cat /proc/sys/net/ipv4/ip_forward
# Должно быть: 1
```

### 7.2. Проверка интерфейсов

```bash
ip addr show
# Проверьте, что eth0 и eth1 имеют правильные IP адреса
```

### 7.3. Проверка маршрутизации

```bash
ip route show
# Должны быть маршруты для обеих сетей
```

### 7.4. Проверка NAT правил

```bash
sudo iptables -t nat -L -n -v
# Должно быть правило MASQUERADE для eth0
```

### 7.5. Проверка FORWARD правил

```bash
sudo iptables -L FORWARD -n -v
# Должны быть правила для eth1 → eth0 и обратно
```

### 7.6. Тест подключения с IoT устройства

На IoT устройстве выполните:

```bash
# Проверка gateway
ping 192.168.1.1

# Проверка интернета
ping 8.8.8.8

# Проверка DNS
nslookup google.com
```

---

## 8. Дополнительные настройки безопасности

### 8.1. Ограничение исходящего трафика (опционально)

```bash
# Ограничение скорости (rate limiting)
sudo iptables -A FORWARD -i eth1 -o eth0 -m limit --limit 1000/s -j ACCEPT

# Блокировка определенных портов (например, порт 25 для SMTP)
sudo iptables -A FORWARD -i eth1 -o eth0 -p tcp --dport 25 -j DROP
```

### 8.2. Логирование подозрительного трафика

```bash
# Логирование всех новых соединений
sudo iptables -A FORWARD -i eth1 -o eth0 -m state --state NEW -j LOG --log-prefix "NEW-CONN: "
```

---

## 9. Скрипт автоматической настройки (опционально)

Создайте скрипт `/usr/local/bin/setup-sentinel-network.sh`:

```bash
#!/bin/bash
set -e

# Включение IP forwarding
echo "Включение IP forwarding..."
echo 1 > /proc/sys/net/ipv4/ip_forward
sysctl -w net.ipv4.ip_forward=1

# Настройка NAT
echo "Настройка NAT..."
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# Настройка FORWARD правил
echo "Настройка FORWARD правил..."
iptables -A FORWARD -i eth1 -o eth0 -j ACCEPT
iptables -A FORWARD -i eth0 -o eth1 -m state --state RELATED,ESTABLISHED -j ACCEPT

# Сохранение правил
echo "Сохранение правил iptables..."
iptables-save > /etc/iptables/rules.v4

echo "Настройка завершена!"
```

Сделайте исполняемым:

```bash
sudo chmod +x /usr/local/bin/setup-sentinel-network.sh
```

---

## 10. Troubleshooting

### Проблема: IoT устройства не могут выйти в интернет

1. Проверьте IP forwarding: `cat /proc/sys/net/ipv4/ip_forward`
2. Проверьте NAT правила: `sudo iptables -t nat -L -n -v`
3. Проверьте FORWARD правила: `sudo iptables -L FORWARD -n -v`
4. Проверьте маршруты: `ip route show`

### Проблема: DHCP не работает

1. Проверьте статус dnsmasq: `sudo systemctl status dnsmasq`
2. Проверьте логи: `sudo tail -f /var/log/syslog | grep dnsmasq`
3. Убедитесь, что интерфейс eth1 указан в конфиге dnsmasq

### Проблема: Не работает захват трафика

1. Убедитесь, что tcpdump запущен с правами root
2. Проверьте, что интерфейс eth1 существует: `ip link show eth1`
3. Проверьте, что на интерфейсе есть трафик: `sudo tcpdump -i eth1 -c 10`

---

## Заключение

После выполнения всех шагов Orange Pi будет:
- ✅ Выполнять роль Gateway для IoT устройств
- ✅ Обеспечивать NAT для выхода в интернет
- ✅ Предоставлять DHCP сервис
- ✅ Готов к захвату трафика для анализа аномалий

Следующий шаг: запуск ML Backend и Traffic Pipeline для анализа трафика.

