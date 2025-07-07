#!/usr/bin/env python3
"""
Автономный мониторинг бота для 24/7 работы
Проверяет webhook и восстанавливает при необходимости
"""

import requests
import time
import os
import logging
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/bot_monitor.log'),
        logging.StreamHandler()
    ]
)

class BotMonitor:
    def __init__(self):
        load_dotenv('/app/backend/.env')
        self.token = os.environ.get('TELEGRAM_TOKEN')
        
        # Determine environment and URLs
        environment = os.environ.get('ENVIRONMENT', 'development')
        if environment == 'production':
            self.backend_url = 'https://baseshinomontaz.store'
            self.webhook_url = 'https://baseshinomontaz.store/webhook.php'
        else:
            # Development environment
            self.backend_url = 'https://8867069a-d008-4da6-8b30-bdb8e855fcb4.preview.emergentagent.com'
            self.webhook_url = 'https://baseshinomontaz.store/webhook.php'
        
        if not self.token:
            raise ValueError("TELEGRAM_TOKEN not found")
            
    def check_webhook(self):
        """Проверка состояния webhook"""
        try:
            response = requests.get(f'https://api.telegram.org/bot{self.token}/getWebhookInfo', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    webhook_info = data.get('result', {})
                    current_url = webhook_info.get('url', '')
                    
                    if current_url == self.webhook_url:
                        logging.info("✅ Webhook OK")
                        return True
                    else:
                        logging.warning(f"❌ Webhook URL mismatch: {current_url}")
                        return False
                else:
                    logging.error(f"❌ Telegram API error: {data}")
                    return False
            else:
                logging.error(f"❌ HTTP error: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"❌ Webhook check failed: {e}")
            return False
    
    def set_webhook(self):
        """Установка webhook"""
        try:
            response = requests.post(
                f'https://api.telegram.org/bot{self.token}/setWebhook',
                json={'url': self.webhook_url},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    logging.info("✅ Webhook установлен успешно")
                    return True
                else:
                    logging.error(f"❌ Ошибка установки webhook: {data}")
                    return False
            else:
                logging.error(f"❌ HTTP ошибка при установке webhook: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"❌ Ошибка установки webhook: {e}")
            return False
    
    def check_backend_health(self):
        """Проверка здоровья backend"""
        try:
            response = requests.get(f'{self.backend_url}/api/health', timeout=5)
            if response.status_code == 200:
                logging.info("✅ Backend здоров")
                return True
            else:
                logging.warning(f"❌ Backend нездоров: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"❌ Backend недоступен: {e}")
            return False
    
    def monitor_loop(self):
        """Основной цикл мониторинга"""
        logging.info("🤖 Запуск мониторинга бота...")
        
        while True:
            try:
                # Проверка backend
                backend_ok = self.check_backend_health()
                
                # Проверка webhook
                webhook_ok = self.check_webhook()
                
                # Восстановление webhook при необходимости
                if backend_ok and not webhook_ok:
                    logging.info("🔧 Восстанавливаю webhook...")
                    self.set_webhook()
                
                # Ожидание следующей проверки
                time.sleep(60)  # Проверка каждую минуту
                
            except KeyboardInterrupt:
                logging.info("⏹️ Остановка мониторинга")
                break
            except Exception as e:
                logging.error(f"❌ Ошибка в цикле мониторинга: {e}")
                time.sleep(30)  # При ошибке ждем меньше

if __name__ == "__main__":
    monitor = BotMonitor()
    monitor.monitor_loop()