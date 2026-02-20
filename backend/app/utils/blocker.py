"""
Модуль для блокировки IP-адресов на уровне iptables.

Блокировка управляется флагом ENABLE_BLOCKING.
"""

import logging
import platform
import subprocess
from typing import Final


logger = logging.getLogger(__name__)


# Глобальный флаг: включать ли реальную блокировку.
# Для безопасного запуска в dev/на macOS имеет смысл держать False.
ENABLE_BLOCKING: Final[bool] = True


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

    # Команда iptables для блокировки входящего трафика с указанного IP
    cmd = ["sudo", "iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"]

    logger.info("Выполняем блокировку IP через iptables: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info("IP %s успешно заблокирован через iptables.", ip)
    except subprocess.CalledProcessError as exc:
        logger.error(
            "Ошибка при выполнении iptables для IP %s: %s",
            ip,
            exc.stderr or exc.stdout,
        )


