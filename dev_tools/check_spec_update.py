#!/usr/bin/env python3
"""
Автоматическое напоминание об обновлении спецификации
Запускается при изменениях в ключевых файлах
"""

import os
import sys
from datetime import datetime

def check_spec_update_needed():
    """Проверка необходимости обновления спецификации"""
    
    print("🔍 Проверка необходимости обновления технической спецификации...")
    
    # Критичные файлы для мониторинга
    critical_files = [
        "/app/backend/server.py",
        "/app/backend/requirements.txt", 
        "/app/backend/.env",
        "/app/frontend/package.json",
        "/app/frontend/.env",
        "/etc/supervisor/conf.d/supervisord.conf"
    ]
    
    spec_file = "/app/documentation/TECHNICAL_SPEC.md"
    
    # Получаем время последнего изменения спецификации
    try:
        spec_mtime = os.path.getmtime(spec_file)
    except FileNotFoundError:
        print("❌ Техническая спецификация не найдена!")
        return True
    
    # Проверяем изменения в критичных файлах
    newer_files = []
    for file_path in critical_files:
        if os.path.exists(file_path):
            file_mtime = os.path.getmtime(file_path)
            if file_mtime > spec_mtime:
                newer_files.append(file_path)
    
    if newer_files:
        print("⚠️  ВНИМАНИЕ: Обнаружены изменения в критичных файлах:")
        for file_path in newer_files:
            print(f"   📄 {file_path}")
        
        print("\n📋 ТРЕБУЕТСЯ обновить техническую спецификацию:")
        print(f"   📝 {spec_file}")
        
        print("\n🔧 Что нужно обновить:")
        print("   1. Версию и дату в заголовке")
        print("   2. Соответствующие разделы")
        print("   3. Запись в 'История изменений'")
        
        print(f"\n📅 Последнее обновление спецификации: {datetime.fromtimestamp(spec_mtime)}")
        print(f"📅 Текущее время: {datetime.now()}")
        
        return True
    else:
        print("✅ Техническая спецификация актуальна")
        return False

def main():
    """Основная функция"""
    update_needed = check_spec_update_needed()
    
    if update_needed:
        print("\n" + "="*60)
        print("🚨 НАПОМИНАНИЕ: Обновите техническую спецификацию!")
        print("📖 Инструкции: /app/documentation/UPDATE_RULES.md")
        print("="*60)
        sys.exit(1)
    else:
        print("\n✅ Проверка завершена - обновление не требуется")
        sys.exit(0)

if __name__ == "__main__":
    main()