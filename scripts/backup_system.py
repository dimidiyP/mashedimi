#!/usr/bin/env python3
"""
Автоматическая система бэкапов для Telegram Bot
- Создает ежедневные бэкапы кода и базы данных
- Автоматически удаляет бэкапы старше 30 дней
- Логирует все операции
"""

import os
import shutil
import subprocess
import datetime
import glob
import logging
from pathlib import Path
import zipfile
import asyncio
import motor.motor_asyncio
from bson import json_util
import json

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/backup_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BackupSystem:
    def __init__(self):
        self.app_dir = Path("/app")
        self.backup_dir = Path("/app/backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        # MongoDB connection
        self.mongo_url = os.environ.get('MONGO_URL', 'mongodb://127.0.0.1:27017')
        
        # Retention period (days)
        self.retention_days = 30
        
    def create_timestamp(self):
        """Создать timestamp для имени бэкапа"""
        return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    def backup_code(self):
        """Создать бэкап кода приложения"""
        try:
            timestamp = self.create_timestamp()
            backup_name = f"code_backup_{timestamp}"
            backup_path = self.backup_dir / backup_name
            
            logger.info(f"Starting code backup: {backup_name}")
            
            # Создать директорию бэкапа
            backup_path.mkdir(exist_ok=True)
            
            # Копировать важные директории и файлы
            important_paths = [
                "backend",
                "frontend", 
                "scripts",
                "documentation",
                "README.md",
                "test_result.md"
            ]
            
            for path_name in important_paths:
                source_path = self.app_dir / path_name
                if source_path.exists():
                    dest_path = backup_path / path_name
                    
                    if source_path.is_dir():
                        shutil.copytree(source_path, dest_path, ignore=shutil.ignore_patterns(
                            '__pycache__', '*.pyc', 'node_modules', '*.log', 'yarn.lock'
                        ))
                    else:
                        shutil.copy2(source_path, dest_path)
                    
                    logger.info(f"Copied: {path_name}")
            
            # Создать ZIP архив
            zip_path = self.backup_dir / f"{backup_name}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in backup_path.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(backup_path)
                        zipf.write(file_path, arcname)
            
            # Удалить временную директорию
            shutil.rmtree(backup_path)
            
            logger.info(f"Code backup completed: {zip_path}")
            return zip_path
            
        except Exception as e:
            logger.error(f"Code backup failed: {str(e)}")
            return None
    
    async def backup_database(self):
        """Создать бэкап базы данных MongoDB"""
        try:
            timestamp = self.create_timestamp()
            backup_name = f"database_backup_{timestamp}.json"
            backup_path = self.backup_dir / backup_name
            
            logger.info(f"Starting database backup: {backup_name}")
            
            # Подключение к MongoDB
            client = motor.motor_asyncio.AsyncIOMotorClient(self.mongo_url)
            db = client.telegram_bot_db
            
            backup_data = {}
            
            # Бэкап всех коллекций
            collections = await db.list_collection_names()
            
            for collection_name in collections:
                logger.info(f"Backing up collection: {collection_name}")
                collection = db[collection_name]
                
                # Получить все документы
                documents = []
                async for doc in collection.find():
                    documents.append(doc)
                
                backup_data[collection_name] = documents
                logger.info(f"Collection {collection_name}: {len(documents)} documents")
            
            # Сохранить в JSON файл
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, default=json_util.default, ensure_ascii=False, indent=2)
            
            client.close()
            
            # Создать сжатый архив
            zip_path = backup_path.with_suffix('.zip')
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(backup_path, backup_path.name)
            
            # Удалить JSON файл
            backup_path.unlink()
            
            logger.info(f"Database backup completed: {zip_path}")
            return zip_path
            
        except Exception as e:
            logger.error(f"Database backup failed: {str(e)}")
            return None
    
    def cleanup_old_backups(self):
        """Удалить бэкапы старше retention_days дней"""
        try:
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=self.retention_days)
            cutoff_timestamp = cutoff_date.strftime('%Y%m%d')
            
            logger.info(f"Cleaning up backups older than {self.retention_days} days (before {cutoff_timestamp})")
            
            # Найти все файлы бэкапов
            backup_patterns = [
                "code_backup_*.zip",
                "database_backup_*.zip",
                "full_backup_*.zip"
            ]
            
            deleted_count = 0
            
            for pattern in backup_patterns:
                for backup_file in self.backup_dir.glob(pattern):
                    # Извлечь timestamp из имени файла
                    filename = backup_file.stem
                    try:
                        # Найти timestamp в имени файла (YYYYMMDD_HHMMSS)
                        timestamp_part = filename.split('_')[-2]  # Получить YYYYMMDD
                        
                        if timestamp_part < cutoff_timestamp:
                            backup_file.unlink()
                            logger.info(f"Deleted old backup: {backup_file.name}")
                            deleted_count += 1
                            
                    except (IndexError, ValueError):
                        logger.warning(f"Could not parse timestamp from {backup_file.name}")
            
            logger.info(f"Cleanup completed: {deleted_count} old backups deleted")
            
        except Exception as e:
            logger.error(f"Backup cleanup failed: {str(e)}")
    
    def get_backup_stats(self):
        """Получить статистику бэкапов"""
        try:
            backup_files = list(self.backup_dir.glob("*.zip"))
            total_size = sum(f.stat().st_size for f in backup_files)
            
            stats = {
                "total_backups": len(backup_files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "backup_directory": str(self.backup_dir),
                "retention_days": self.retention_days
            }
            
            logger.info(f"Backup stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get backup stats: {str(e)}")
            return None
    
    async def create_full_backup(self):
        """Создать полный бэкап (код + база данных)"""
        try:
            timestamp = self.create_timestamp()
            logger.info(f"Starting full backup: {timestamp}")
            
            # Создать бэкап кода
            code_backup = self.backup_code()
            
            # Создать бэкап базы данных  
            db_backup = await self.backup_database()
            
            if code_backup and db_backup:
                # Создать объединенный архив
                full_backup_path = self.backup_dir / f"full_backup_{timestamp}.zip"
                
                with zipfile.ZipFile(full_backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # Добавить бэкап кода
                    zipf.write(code_backup, f"code_{code_backup.name}")
                    
                    # Добавить бэкап базы данных
                    zipf.write(db_backup, f"database_{db_backup.name}")
                
                # Удалить отдельные архивы
                code_backup.unlink()
                db_backup.unlink()
                
                logger.info(f"Full backup completed: {full_backup_path}")
                return full_backup_path
            else:
                logger.error("Full backup failed - one or both components failed")
                return None
                
        except Exception as e:
            logger.error(f"Full backup failed: {str(e)}")
            return None

async def main():
    """Основная функция для запуска бэкапа"""
    backup_system = BackupSystem()
    
    logger.info("=== BACKUP SYSTEM STARTED ===")
    
    # Создать полный бэкап
    backup_path = await backup_system.create_full_backup()
    
    if backup_path:
        logger.info(f"✅ Backup successful: {backup_path}")
    else:
        logger.error("❌ Backup failed")
    
    # Очистить старые бэкапы
    backup_system.cleanup_old_backups()
    
    # Показать статистику
    stats = backup_system.get_backup_stats()
    if stats:
        logger.info(f"📊 Backup statistics: {stats}")
    
    logger.info("=== BACKUP SYSTEM COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(main())