"""Services for food and health functionality"""

import logging
import json
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
import openai
from openai import OpenAI

from config.settings import settings
from config.database import db_manager
from config.constants import COLLECTION_FOOD_ANALYSIS, COLLECTION_HEALTH_PROFILES, COLLECTION_WORKOUTS, COLLECTION_STEPS
from core.utils import (
    download_image_as_base64, validate_nutrition_data, 
    format_nutrition_text, parse_json_response, get_date_range
)
from .models import (
    FoodAnalysis, FoodItem, NutritionData, HealthProfile, 
    WorkoutSession, StepsData
)

logger = logging.getLogger(__name__)

class FoodAnalysisService:
    """Service for food analysis using OpenAI Vision API"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
    async def analyze_food_image(self, image_base64: str, user_id: int, chat_id: int, message_id: int) -> Optional[FoodAnalysis]:
        """Analyze food image using OpenAI Vision API"""
        try:
            start_time = datetime.now()
            
            # Prepare prompt for food analysis
            prompt = self._get_food_analysis_prompt()
            
            # Try with primary model first
            try:
                response = await self._call_openai_vision(
                    image_base64, prompt, settings.OPENAI_MODEL_DEFAULT
                )
                model_used = settings.OPENAI_MODEL_DEFAULT
            except Exception as e:
                logger.warning(f"Primary model failed, trying fallback: {e}")
                response = await self._call_openai_vision(
                    image_base64, prompt, settings.OPENAI_MODEL_FALLBACK
                )
                model_used = settings.OPENAI_MODEL_FALLBACK
            
            # Parse AI response
            analysis_data = parse_json_response(response)
            if not analysis_data:
                logger.error("Failed to parse AI response")
                return None
            
            # Create food analysis object
            food_analysis = self._create_food_analysis_from_ai(
                analysis_data, user_id, chat_id, message_id, image_base64, model_used
            )
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            food_analysis.processing_time = processing_time
            
            # Save to database
            await self._save_food_analysis(food_analysis)
            
            logger.info(f"Food analysis completed for user {user_id} in {processing_time:.2f}s")
            return food_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing food image: {e}")
            return None
    
    async def _call_openai_vision(self, image_base64: str, prompt: str, model: str) -> str:
        """Call OpenAI Vision API"""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI Vision API error: {e}")
            raise
    
    def _get_food_analysis_prompt(self) -> str:
        """Get prompt for food analysis"""
        return """
Проанализируй изображение еды и верни результат в формате JSON.

ВАЖНО: Верни ТОЛЬКО JSON без дополнительного текста.

Формат ответа:
{
  "food_items": [
    {
      "name": "название блюда",
      "description": "описание блюда",
      "portion_size": число_граммов,
      "nutrition": {
        "calories": число_калорий,
        "protein": число_белков_в_граммах,
        "carbs": число_углеводов_в_граммах,
        "fat": число_жиров_в_граммах,
        "fiber": число_клетчатки_в_граммах,
        "sugar": число_сахара_в_граммах
      },
      "confidence": число_от_0_до_1
    }
  ]
}

ПРИМЕРЫ реальных значений:
- Бутерброд с сыром (150г): 320 ккал, 12г белков, 15г жиров, 30г углеводов
- Йогурт с ягодами (200г): 150 ккал, 6г белков, 3г жиров, 20г углеводов
- Яблоко среднее (180г): 95 ккал, 0.5г белков, 0.3г жиров, 25г углеводов
- Куриная грудка (100г): 165 ккал, 31г белков, 3.6г жиров, 0г углеводов

Требования:
1. Определи все видимые блюда на изображении
2. Оцени размер порций в граммах
3. Укажи РЕАЛЬНЫЕ значения калорий и БЖУ (не нули!)
4. Confidence от 0.1 до 1.0 (насколько уверен в определении)
5. Если еды не видно, верни пустой массив food_items
"""
    
    def _create_food_analysis_from_ai(
        self, analysis_data: Dict[str, Any], user_id: int, chat_id: int, 
        message_id: int, image_base64: str, model_used: str
    ) -> FoodAnalysis:
        """Create FoodAnalysis object from AI response"""
        
        food_items = []
        for item_data in analysis_data.get('food_items', []):
            nutrition_data = item_data.get('nutrition', {})
            
            nutrition = NutritionData(
                calories=nutrition_data.get('calories', 0),
                protein=nutrition_data.get('protein', 0),
                carbs=nutrition_data.get('carbs', 0),
                fat=nutrition_data.get('fat', 0),
                fiber=nutrition_data.get('fiber'),
                sugar=nutrition_data.get('sugar')
            )
            
            food_item = FoodItem(
                name=item_data.get('name', 'Неопознанное блюдо'),
                description=item_data.get('description', ''),
                portion_size=item_data.get('portion_size', 100.0),
                nutrition=nutrition,
                confidence=item_data.get('confidence', 0.5),
                image_base64=image_base64
            )
            
            food_items.append(food_item)
        
        # Create analysis object
        food_analysis = FoodAnalysis(
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            food_items=food_items,
            ai_model_used=model_used
        )
        
        # Calculate total nutrition
        food_analysis.total_nutrition = food_analysis.calculate_total_nutrition()
        
        return food_analysis
    
    async def _save_food_analysis(self, food_analysis: FoodAnalysis) -> None:
        """Save food analysis to database"""
        try:
            collection = db_manager.get_collection(COLLECTION_FOOD_ANALYSIS)
            collection.insert_one(food_analysis.to_dict())
            logger.info(f"Food analysis saved for user {food_analysis.user_id}")
        except Exception as e:
            logger.error(f"Error saving food analysis: {e}")
            raise
    
    async def get_user_food_statistics(
        self, user_id: int, period: str = "week"
    ) -> Dict[str, Any]:
        """Get user food statistics for a period"""
        try:
            start_date, end_date = get_date_range(period)
            
            collection = db_manager.get_collection(COLLECTION_FOOD_ANALYSIS)
            
            # Aggregation pipeline
            pipeline = [
                {
                    "$match": {
                        "user_id": user_id,
                        "analysis_timestamp": {"$gte": start_date, "$lte": end_date}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_calories": {"$sum": "$total_nutrition.calories"},
                        "total_protein": {"$sum": "$total_nutrition.protein"},
                        "total_carbs": {"$sum": "$total_nutrition.carbs"},
                        "total_fat": {"$sum": "$total_nutrition.fat"},
                        "meal_count": {"$sum": 1},
                        "avg_calories_per_meal": {"$avg": "$total_nutrition.calories"}
                    }
                }
            ]
            
            result = list(collection.aggregate(pipeline))
            
            if result:
                stats = result[0]
                return {
                    "period": period,
                    "total_calories": round(stats.get("total_calories", 0), 1),
                    "total_protein": round(stats.get("total_protein", 0), 1),
                    "total_carbs": round(stats.get("total_carbs", 0), 1),
                    "total_fat": round(stats.get("total_fat", 0), 1),
                    "meal_count": stats.get("meal_count", 0),
                    "avg_calories_per_meal": round(stats.get("avg_calories_per_meal", 0), 1)
                }
            else:
                return {
                    "period": period,
                    "total_calories": 0,
                    "total_protein": 0,
                    "total_carbs": 0,
                    "total_fat": 0,
                    "meal_count": 0,
                    "avg_calories_per_meal": 0
                }
                
        except Exception as e:
            logger.error(f"Error getting food statistics: {e}")
            return {}
    
    async def search_food_database(
        self, user_id: int, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search user's food database"""
        try:
            collection = db_manager.get_collection(COLLECTION_FOOD_ANALYSIS)
            
            # Create search query
            search_query = {
                "user_id": user_id,
                "$or": [
                    {"food_items.name": {"$regex": query, "$options": "i"}},
                    {"food_items.description": {"$regex": query, "$options": "i"}}
                ]
            }
            
            results = collection.find(search_query).limit(limit).sort("analysis_timestamp", -1)
            
            found_items = []
            for analysis in results:
                for food_item in analysis.get("food_items", []):
                    if (query.lower() in food_item.get("name", "").lower() or 
                        query.lower() in food_item.get("description", "").lower()):
                        
                        found_items.append({
                            "name": food_item.get("name"),
                            "description": food_item.get("description"),
                            "nutrition": food_item.get("nutrition"),
                            "portion_size": food_item.get("portion_size"),
                            "date": analysis.get("analysis_timestamp")
                        })
            
            return found_items
            
        except Exception as e:
            logger.error(f"Error searching food database: {e}")
            return []

class HealthProfileService:
    """Service for managing user health profiles"""
    
    async def get_or_create_profile(self, user_id: int) -> HealthProfile:
        """Get existing profile or create new one"""
        try:
            collection = db_manager.get_collection(COLLECTION_HEALTH_PROFILES)
            
            # Try to find existing profile
            existing = collection.find_one({"user_id": user_id})
            
            if existing:
                return HealthProfile.from_dict(existing)
            else:
                # Create new profile
                profile = HealthProfile(user_id=user_id)
                collection.insert_one(profile.to_dict())
                logger.info(f"Created new health profile for user {user_id}")
                return profile
                
        except Exception as e:
            logger.error(f"Error getting/creating health profile: {e}")
            return HealthProfile(user_id=user_id)
    
    async def update_profile(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """Update health profile"""
        try:
            collection = db_manager.get_collection(COLLECTION_HEALTH_PROFILES)
            
            # Add updated timestamp
            updates["updated_at"] = datetime.now()
            
            result = collection.update_one(
                {"user_id": user_id},
                {"$set": updates},
                upsert=True
            )
            
            logger.info(f"Updated health profile for user {user_id}")
            return result.modified_count > 0 or result.upserted_id is not None
            
        except Exception as e:
            logger.error(f"Error updating health profile: {e}")
            return False
    
    async def get_daily_goals(self, user_id: int) -> Dict[str, float]:
        """Get calculated daily nutrition goals"""
        try:
            profile = await self.get_or_create_profile(user_id)
            return profile.calculate_daily_goals()
        except Exception as e:
            logger.error(f"Error calculating daily goals: {e}")
            return {}
    
    async def save_workout(self, workout: WorkoutSession) -> bool:
        """Save workout session"""
        try:
            collection = db_manager.get_collection(COLLECTION_WORKOUTS)
            collection.insert_one(workout.to_dict())
            logger.info(f"Saved workout for user {workout.user_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving workout: {e}")
            return False
    
    async def save_steps(self, steps_data: StepsData) -> bool:
        """Save daily steps data"""
        try:
            collection = db_manager.get_collection(COLLECTION_STEPS)
            
            # Update or insert for the specific date
            result = collection.update_one(
                {
                    "user_id": steps_data.user_id,
                    "date": steps_data.date
                },
                {"$set": steps_data.to_dict()},
                upsert=True
            )
            
            logger.info(f"Saved steps data for user {steps_data.user_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving steps: {e}")
            return False
    
    async def get_fitness_summary(self, user_id: int, period: str = "week") -> Dict[str, Any]:
        """Get fitness activity summary"""
        try:
            start_date, end_date = get_date_range(period)
            
            # Get workouts
            workouts_collection = db_manager.get_collection(COLLECTION_WORKOUTS)
            workouts = list(workouts_collection.find({
                "user_id": user_id,
                "timestamp": {"$gte": start_date, "$lte": end_date}
            }))
            
            # Get steps
            steps_collection = db_manager.get_collection(COLLECTION_STEPS)
            steps = list(steps_collection.find({
                "user_id": user_id,
                "date": {"$gte": start_date, "$lte": end_date}
            }))
            
            # Calculate summary
            total_workouts = len(workouts)
            total_workout_time = sum(w.get("duration", 0) for w in workouts)
            total_workout_calories = sum(w.get("calories_burned", 0) for w in workouts)
            
            total_steps = sum(s.get("steps", 0) for s in steps)
            avg_daily_steps = total_steps / max(len(steps), 1)
            
            return {
                "period": period,
                "total_workouts": total_workouts,
                "total_workout_time": round(total_workout_time, 1),
                "total_workout_calories": round(total_workout_calories, 1),
                "total_steps": total_steps,
                "avg_daily_steps": round(avg_daily_steps, 0),
                "active_days": len(steps)
            }
            
        except Exception as e:
            logger.error(f"Error getting fitness summary: {e}")
            return {}

class HealthAIService:
    """AI service for personalized health recommendations"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.food_service = FoodAnalysisService()
        self.profile_service = HealthProfileService()
    
    async def get_personalized_recommendation(
        self, user_id: int, request_type: str = "general"
    ) -> str:
        """Get personalized health recommendation"""
        try:
            # Gather user data
            profile = await self.profile_service.get_or_create_profile(user_id)
            food_stats = await self.food_service.get_user_food_statistics(user_id, "week")
            fitness_summary = await self.profile_service.get_fitness_summary(user_id, "week")
            daily_goals = await self.profile_service.get_daily_goals(user_id)
            
            # Create personalized prompt
            prompt = self._create_health_prompt(
                profile, food_stats, fitness_summary, daily_goals, request_type
            )
            
            # Get AI recommendation
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL_DEFAULT,
                messages=[
                    {"role": "system", "content": "Ты персональный AI-консультант по здоровью и питанию. Давай практические, научно обоснованные советы на основе данных пользователя."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error getting health recommendation: {e}")
            return "Извините, не удалось получить персональную рекомендацию. Попробуйте позже."
    
    def _create_health_prompt(
        self, profile: HealthProfile, food_stats: Dict, 
        fitness_summary: Dict, daily_goals: Dict, request_type: str
    ) -> str:
        """Create personalized health prompt"""
        
        # Profile info
        profile_info = f"""
ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:
- Возраст: {profile.age or 'не указан'}
- Пол: {profile.gender or 'не указан'}
- Рост: {profile.height or 'не указан'} см
- Вес: {profile.weight or 'не указан'} кг
- Уровень активности: {profile.activity_level}
- Цель: {profile.fitness_goal}
- Ограничения в питании: {', '.join(profile.dietary_restrictions) if profile.dietary_restrictions else 'нет'}
- Аллергии: {', '.join(profile.allergies) if profile.allergies else 'нет'}
"""
        
        # Food stats
        food_info = f"""
ПИТАНИЕ ЗА НЕДЕЛЮ:
- Общие калории: {food_stats.get('total_calories', 0)} ккал
- Белки: {food_stats.get('total_protein', 0)} г
- Углеводы: {food_stats.get('total_carbs', 0)} г
- Жиры: {food_stats.get('total_fat', 0)} г
- Количество приемов пищи: {food_stats.get('meal_count', 0)}
- Средние калории на прием: {food_stats.get('avg_calories_per_meal', 0)} ккал
"""
        
        # Fitness info
        fitness_info = f"""
АКТИВНОСТЬ ЗА НЕДЕЛЮ:
- Тренировок: {fitness_summary.get('total_workouts', 0)}
- Время тренировок: {fitness_summary.get('total_workout_time', 0)} мин
- Сожжено калорий: {fitness_summary.get('total_workout_calories', 0)} ккал
- Общие шаги: {fitness_summary.get('total_steps', 0)}
- Средние шаги в день: {fitness_summary.get('avg_daily_steps', 0)}
- Активных дней: {fitness_summary.get('active_days', 0)}
"""
        
        # Daily goals
        goals_info = ""
        if daily_goals:
            goals_info = f"""
ДНЕВНЫЕ ЦЕЛИ:
- Калории: {daily_goals.get('calories', 0):.0f} ккал
- Белки: {daily_goals.get('protein', 0):.0f} г
- Углеводы: {daily_goals.get('carbs', 0):.0f} г
- Жиры: {daily_goals.get('fat', 0):.0f} г
"""
        
        # Request type specific instructions
        request_instructions = {
            "general": "Дай общую оценку здоровья и образа жизни с практическими советами.",
            "nutrition": "Сосредоточься на питании: что улучшить, какие продукты добавить/убрать.",
            "fitness": "Дай рекомендации по физической активности и тренировкам.",
            "goals": "Помоги скорректировать цели и план для их достижения."
        }
        
        instruction = request_instructions.get(request_type, request_instructions["general"])
        
        return f"""
{profile_info}
{food_info}
{fitness_info}
{goals_info}

ЗАДАЧА: {instruction}

Дай персональные рекомендации в дружелюбном тоне. Укажи конкретные действия, которые можно предпринять сегодня/на этой неделе. Если данных недостаточно, посоветуй что отслеживать дополнительно.
"""