#!/usr/bin/env python3
"""
Демон для автоматических бэкапов без cron
Запускается как supervisor процесс и делает бэкапы каждые 24 часа
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta
import sys
import os

# Добавить путь к основным модулям
sys.path.append('/app/scripts')

from backup_system import BackupSystem

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/backup_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BackupDaemon:
    def __init__(self):
        self.backup_system = BackupSystem()
        self.backup_interval = 24 * 60 * 60  # 24 hours in seconds
        self.last_backup = None
        
    async def run_backup(self):
        """Выполнить бэкап"""
        try:
            logger.info("🔄 Starting scheduled backup...")
            
            backup_path = await self.backup_system.create_full_backup()
            
            if backup_path:
                logger.info(f"✅ Scheduled backup successful: {backup_path}")
                self.last_backup = datetime.now()
                
                # Очистить старые бэкапы
                self.backup_system.cleanup_old_backups()
                
                # Показать статистику
                stats = self.backup_system.get_backup_stats()
                if stats:
                    logger.info(f"📊 Backup stats: {stats}")
                    
                return True
            else:
                logger.error("❌ Scheduled backup failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Backup error: {str(e)}")
            return False
    
    def should_run_backup(self):
        """Проверить, нужно ли делать бэкап"""
        if self.last_backup is None:
            return True
            
        time_since_backup = datetime.now() - self.last_backup
        return time_since_backup.total_seconds() >= self.backup_interval
    
    async def run_daemon(self):
        """Основной цикл демона"""
        logger.info("🚀 Backup daemon started")
        logger.info(f"📅 Backup interval: {self.backup_interval / 3600} hours")
        
        # Проверить, есть ли существующие бэкапы
        stats = self.backup_system.get_backup_stats()
        if stats and stats['total_backups'] > 0:
            logger.info(f"📦 Found {stats['total_backups']} existing backups")
        else:
            # Сделать первоначальный бэкап
            logger.info("🔄 Creating initial backup...")
            await self.run_backup()
        
        while True:
            try:
                if self.should_run_backup():
                    await self.run_backup()
                else:
                    # Показать время до следующего бэкапа
                    if self.last_backup:
                        next_backup = self.last_backup + timedelta(seconds=self.backup_interval)
                        logger.info(f"⏰ Next backup scheduled for: {next_backup.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Ждать 1 час перед следующей проверкой
                await asyncio.sleep(3600)  # 1 hour
                
            except KeyboardInterrupt:
                logger.info("🛑 Backup daemon stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Daemon error: {str(e)}")
                # Ждать 5 минут перед повторной попыткой
                await asyncio.sleep(300)

async def main():
    """Точка входа"""
    daemon = BackupDaemon()
    await daemon.run_daemon()

if __name__ == "__main__":
    asyncio.run(main())