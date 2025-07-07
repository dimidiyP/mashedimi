#!/bin/bash
# Скрипт для настройки автоматических бэкапов

# Создать директорию для бэкапов
mkdir -p /app/backups

# Сделать скрипт бэкапа исполняемым  
chmod +x /app/scripts/backup_system.py

# Добавить cron задачу для ежедневного бэкапа в 2:00
(crontab -l 2>/dev/null; echo "0 2 * * * cd /app && /usr/bin/python3 /app/scripts/backup_system.py >> /var/log/backup_cron.log 2>&1") | crontab -

# Добавить задачу для еженедельного полного бэкапа в воскресенье в 1:00
(crontab -l 2>/dev/null; echo "0 1 * * 0 cd /app && /usr/bin/python3 /app/scripts/backup_system.py >> /var/log/backup_weekly.log 2>&1") | crontab -

echo "✅ Автоматические бэкапы настроены:"
echo "   - Ежедневно в 02:00"  
echo "   - Еженедельно в воскресенье в 01:00"
echo "   - Логи: /var/log/backup_cron.log"
echo "   - Хранение: 30 дней"
echo "   - Директория: /app/backups"

# Показать текущие cron задачи
echo ""
echo "Текущие cron задачи:"
crontab -l