#!/usr/bin/env python3
"""
Система отладки для реального тестирования бота
Детальное логирование всех взаимодействий для анализа
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import asyncio

class DebugLogger:
    """Система детального логирования для отладки"""
    
    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.debug_file = Path("/var/log/bot_debug.log")
        self.interactions_file = Path("/var/log/bot_interactions.json")
        
        # Create debug logger
        self.logger = logging.getLogger("bot_debug")
        self.logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
        
        if debug_mode:
            # File handler for debug logs
            file_handler = logging.FileHandler(self.debug_file)
            file_handler.setLevel(logging.DEBUG)
            
            # Detailed formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            
        # Interaction storage
        self.interactions = []
    
    def log_user_interaction(self, 
                           user_id: int, 
                           username: str,
                           interaction_type: str,
                           input_data: Any,
                           output_data: Any = None,
                           response_time: float = None,
                           error: str = None,
                           context: Dict = None):
        """Записать взаимодействие пользователя"""
        
        if not self.debug_mode:
            return
        
        interaction = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "username": username,
            "interaction_type": interaction_type,
            "input_data": self._serialize_data(input_data),
            "output_data": self._serialize_data(output_data),
            "response_time": response_time,
            "error": error,
            "context": context or {},
            "session_id": f"{user_id}_{int(time.time())}"
        }
        
        self.interactions.append(interaction)
        
        # Log to file
        self.logger.debug(f"USER_INTERACTION: {json.dumps(interaction, ensure_ascii=False)}")
        
        # Save to JSON file periodically
        if len(self.interactions) % 10 == 0:
            self._save_interactions()
    
    def log_system_event(self, event_type: str, details: Dict[str, Any]):
        """Записать системное событие"""
        
        if not self.debug_mode:
            return
        
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "details": details
        }
        
        self.logger.debug(f"SYSTEM_EVENT: {json.dumps(event, ensure_ascii=False)}")
    
    def log_openai_request(self, 
                          user_id: int,
                          request_data: Dict,
                          response_data: Dict = None,
                          error: str = None,
                          response_time: float = None):
        """Записать запрос к OpenAI"""
        
        if not self.debug_mode:
            return
        
        openai_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "request": {
                "model": request_data.get("model"),
                "messages_count": len(request_data.get("messages", [])),
                "max_tokens": request_data.get("max_tokens"),
                "has_tools": bool(request_data.get("tools"))
            },
            "response": response_data,
            "error": error,
            "response_time": response_time
        }
        
        self.logger.debug(f"OPENAI_REQUEST: {json.dumps(openai_log, ensure_ascii=False)}")
    
    def log_callback_query(self, 
                          user_id: int,
                          callback_data: str,
                          success: bool = True,
                          error: str = None,
                          response_time: float = None):
        """Записать callback query"""
        
        if not self.debug_mode:
            return
        
        callback_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "callback_data": callback_data,
            "success": success,
            "error": error,
            "response_time": response_time
        }
        
        self.logger.debug(f"CALLBACK_QUERY: {json.dumps(callback_log, ensure_ascii=False)}")
    
    def log_performance_metric(self, 
                              metric_name: str,
                              value: float,
                              user_id: int = None,
                              additional_data: Dict = None):
        """Записать метрику производительности"""
        
        if not self.debug_mode:
            return
        
        metric = {
            "timestamp": datetime.utcnow().isoformat(),
            "metric_name": metric_name,
            "value": value,
            "user_id": user_id,
            "additional_data": additional_data or {}
        }
        
        self.logger.debug(f"PERFORMANCE_METRIC: {json.dumps(metric, ensure_ascii=False)}")
    
    def _serialize_data(self, data: Any) -> Any:
        """Сериализация данных для JSON"""
        if data is None:
            return None
        
        try:
            # Attempt to serialize
            json.dumps(data)
            return data
        except TypeError:
            # Convert to string if not serializable
            return str(data)
    
    def _save_interactions(self):
        """Сохранить взаимодействия в JSON файл"""
        try:
            with open(self.interactions_file, 'w', encoding='utf-8') as f:
                json.dump(self.interactions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save interactions: {str(e)}")
    
    def get_debug_stats(self) -> Dict[str, Any]:
        """Получить статистику отладки"""
        if not self.debug_mode:
            return {"debug_mode": False}
        
        # Count interactions by type
        interaction_types = {}
        total_response_time = 0
        error_count = 0
        
        for interaction in self.interactions:
            itype = interaction["interaction_type"]
            interaction_types[itype] = interaction_types.get(itype, 0) + 1
            
            if interaction.get("response_time"):
                total_response_time += interaction["response_time"]
            
            if interaction.get("error"):
                error_count += 1
        
        avg_response_time = (total_response_time / len(self.interactions)) if self.interactions else 0
        
        return {
            "debug_mode": True,
            "total_interactions": len(self.interactions),
            "interaction_types": interaction_types,
            "error_count": error_count,
            "error_rate": (error_count / len(self.interactions)) if self.interactions else 0,
            "avg_response_time": avg_response_time,
            "debug_file": str(self.debug_file),
            "interactions_file": str(self.interactions_file)
        }
    
    def clear_debug_data(self):
        """Очистить данные отладки"""
        self.interactions.clear()
        
        # Clear log files
        if self.debug_file.exists():
            self.debug_file.unlink()
        
        if self.interactions_file.exists():
            self.interactions_file.unlink()
    
    def export_debug_report(self) -> Dict[str, Any]:
        """Экспортировать отчет отладки"""
        if not self.debug_mode:
            return {"error": "Debug mode is not enabled"}
        
        # Save current interactions
        self._save_interactions()
        
        # Generate summary
        stats = self.get_debug_stats()
        
        # Group interactions by user
        users_data = {}
        for interaction in self.interactions:
            user_id = interaction["user_id"]
            if user_id not in users_data:
                users_data[user_id] = {
                    "username": interaction["username"],
                    "interactions": [],
                    "total_interactions": 0,
                    "errors": 0,
                    "avg_response_time": 0
                }
            
            users_data[user_id]["interactions"].append(interaction)
            users_data[user_id]["total_interactions"] += 1
            
            if interaction.get("error"):
                users_data[user_id]["errors"] += 1
        
        # Calculate averages
        for user_data in users_data.values():
            response_times = [i.get("response_time", 0) for i in user_data["interactions"] if i.get("response_time")]
            user_data["avg_response_time"] = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            "summary": stats,
            "users_data": users_data,
            "export_timestamp": datetime.utcnow().isoformat()
        }

# Глобальный экземпляр отладчика
debug_logger = None

def init_debug_mode(debug_mode: bool = False):
    """Инициализировать режим отладки"""
    global debug_logger
    debug_logger = DebugLogger(debug_mode)
    
    if debug_mode:
        print("🐛 DEBUG MODE ENABLED - Все взаимодействия записываются")
        print(f"📁 Debug logs: /var/log/bot_debug.log")
        print(f"📄 Interactions: /var/log/bot_interactions.json")
    else:
        print("✅ Debug mode disabled")

def get_debug_logger() -> DebugLogger:
    """Получить отладчик"""
    if debug_logger is None:
        raise RuntimeError("Debug logger not initialized")
    return debug_logger

def is_debug_mode() -> bool:
    """Проверить, включен ли режим отладки"""
    return debug_logger is not None and debug_logger.debug_mode