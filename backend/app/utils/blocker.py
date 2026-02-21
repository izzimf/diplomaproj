"""
Модуль для блокировки IP-адресов на уровне iptables.

Блокировка управляется флагом ENABLE_BLOCKING.
"""

import logging
import os
import platform
import subprocess
from typing import Final


logger = logging.getLogger(__name__)


# Глобальный флаг: включать ли реальную блокировку.
# Для безопасного запуска в dev/на macOS имеет смысл держать False.
ENABLE_BLOCKING: Final[bool] = True


def _is_root() -> bool:
    """Проверяет, запущен ли процесс с правами root."""
    return os.geteuid() == 0


def block_ip(ip: str) -> None:
    """
    Блокирует IP-адрес с помощью iptables, если ENABLE_BLOCKING == True и ОС — Linux.

    В проде стратегию блокировки (chain/policy) можно расширить.
    """
    if not ip:
        logger.warning("block_ip вызван с пустым IP, пропускаем.")
        return

    if not ENABLE_BLOCKING:
        logger.info("Блокировка IP выключена (ENABLE_BLOCKING=False). IP=%s", ip)
        return

    system = platform.system()
    if system != "Linux":
        logger.warning(
            "Попытка блокировки IP на не-Linux системе (%s). IP=%s. "
            "Реальная блокировка не будет выполнена.",
            system,
            ip,
        )
        return

    # Проверка прав root
    if not _is_root():
        logger.warning(
            "Блокировка IP требует прав root. Текущий UID: %d. "
            "Запустите приложение с правами root или через sudo. IP=%s",
            os.geteuid(),
            ip,
        )
        # Пробуем использовать sudo (может не сработать без настройки sudoers)
        use_sudo = True
    else:
        use_sudo = False

    # Команды iptables для блокировки трафика от указанного IP
    # Блокируем в FORWARD chain (для трафика от IoT устройств через Gateway)
    # и в INPUT chain (для прямого трафика на Orange Pi)
    commands = [
        ["iptables", "-A", "FORWARD", "-s", ip, "-j", "DROP"],
        ["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"],
    ]

    success_count = 0
    for cmd in commands:
        # Добавляем sudo если нужно
        final_cmd = ["sudo"] + cmd if use_sudo else cmd
        
        logger.info("Выполняем блокировку IP через iptables: %s", " ".join(final_cmd))
        try:
            result = subprocess.run(
                final_cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            success_count += 1
            logger.debug("Правило добавлено: %s", " ".join(final_cmd))
        except subprocess.CalledProcessError as exc:
            error_msg = exc.stderr or exc.stdout or "Неизвестная ошибка"
            logger.error(
                "Ошибка при выполнении iptables для IP %s (команда: %s): %s",
                ip,
                " ".join(final_cmd),
                error_msg,
            )
        except FileNotFoundError:
            logger.error("iptables не найден в PATH. Убедитесь, что iptables установлен.")
            break
        except subprocess.TimeoutExpired:
            logger.error("Таймаут при выполнении iptables для IP %s", ip)
            break

    if success_count > 0:
        logger.info("IP %s успешно заблокирован через iptables (%d правил добавлено).", ip, success_count)
    else:
        logger.warning("Не удалось добавить правила блокировки для IP %s", ip)


