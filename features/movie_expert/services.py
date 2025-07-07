"""Services for movie expert functionality"""

import logging
import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
import openai
from openai import OpenAI

from config.settings import settings
from config.database import db_manager
from config.constants import COLLECTION_MOVIES, COLLECTION_USERS
from core.utils import (
    get_date_range, parse_json_response, is_valid_rating, 
    normalize_rating, extract_movie_keywords
)
from .models import (
    MovieEntry, MovieRecommendation, MovieStats, 
    WatchList, MoviePreferences
)

logger = logging.getLogger(__name__)

class MovieExpertService:
    """Service for movie expert functionality"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def save_movie(self, user_id: int, title: str, rating: float, review: str = "", 
                        watch_date: Optional[datetime] = None, is_series: bool = False) -> bool:
        """Save a watched movie/series"""
        try:
            collection = db_manager.get_collection(COLLECTION_MOVIES)
            
            # Normalize rating
            rating = normalize_rating(rating)
            
            # Create movie entry
            movie_entry = MovieEntry(
                user_id=user_id,
                title=title,
                rating=rating,
                review=review,
                watch_date=watch_date or datetime.now(),
                is_series=is_series
            )
            
            # Try to extract additional info using AI
            movie_info = await self._extract_movie_info(title, is_series)
            if movie_info:
                movie_entry.year = movie_info.get('year')
                movie_entry.genre = movie_info.get('genre', [])
                movie_entry.director = movie_info.get('director')
                movie_entry.duration = movie_info.get('duration')
            
            # Save to database
            collection.insert_one(movie_entry.to_dict())
            
            # Update user stats
            await self._update_user_stats(user_id)
            
            logger.info(f"Saved movie '{title}' for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving movie: {e}")
            return False
    
    async def get_user_movies(self, user_id: int, limit: int = 50) -> List[MovieEntry]:
        """Get user's watched movies"""
        try:
            collection = db_manager.get_collection(COLLECTION_MOVIES)
            
            movies_data = collection.find(
                {"user_id": user_id}
            ).sort("watch_date", -1).limit(limit)
            
            movies = []
            for movie_data in movies_data:
                movies.append(MovieEntry.from_dict(movie_data))
            
            return movies
            
        except Exception as e:
            logger.error(f"Error getting user movies: {e}")
            return []
    
    async def search_user_movies(self, user_id: int, query: str) -> List[MovieEntry]:
        """Search user's movies"""
        try:
            collection = db_manager.get_collection(COLLECTION_MOVIES)
            
            search_query = {
                "user_id": user_id,
                "$or": [
                    {"title": {"$regex": query, "$options": "i"}},
                    {"review": {"$regex": query, "$options": "i"}},
                    {"genre": {"$regex": query, "$options": "i"}},
                    {"director": {"$regex": query, "$options": "i"}}
                ]
            }
            
            movies_data = collection.find(search_query).sort("watch_date", -1).limit(20)
            
            movies = []
            for movie_data in movies_data:
                movies.append(MovieEntry.from_dict(movie_data))
            
            return movies
            
        except Exception as e:
            logger.error(f"Error searching movies: {e}")
            return []
    
    async def get_recommendations(self, user_id: int, count: int = 5) -> List[MovieRecommendation]:
        """Get AI-powered movie recommendations"""
        try:
            # Get user's movie history
            user_movies = await self.get_user_movies(user_id, 100)
            
            if len(user_movies) < 3:
                # Not enough data for recommendations
                return await self._get_popular_recommendations(count)
            
            # Get user preferences
            preferences = await self._analyze_user_preferences(user_movies)
            
            # Generate recommendations using AI
            recommendations = await self._generate_ai_recommendations(
                user_movies, preferences, count
            )
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return []
    
    async def get_user_stats(self, user_id: int) -> MovieStats:
        """Get user movie statistics"""
        try:
            collection = db_manager.get_collection(COLLECTION_MOVIES)
            
            # Aggregation pipeline for stats
            pipeline = [
                {"$match": {"user_id": user_id}},
                {
                    "$group": {
                        "_id": None,
                        "total_movies": {
                            "$sum": {"$cond": [{"$eq": ["$is_series", False]}, 1, 0]}
                        },
                        "total_series": {
                            "$sum": {"$cond": [{"$eq": ["$is_series", True]}, 1, 0]}
                        },
                        "average_rating": {"$avg": "$rating"},
                        "total_watch_time": {"$sum": {"$ifNull": ["$duration", 120]}},
                        "genres": {"$push": "$genre"},
                        "directors": {"$push": "$director"},
                        "highest_rated": {"$max": "$rating"},
                        "lowest_rated": {"$min": "$rating"}
                    }
                }
            ]
            
            result = list(collection.aggregate(pipeline))
            
            if result:
                stats_data = result[0]
                
                # Flatten and count genres
                all_genres = []
                for genre_list in stats_data.get("genres", []):
                    if isinstance(genre_list, list):
                        all_genres.extend(genre_list)
                
                # Count genre frequency
                genre_counts = {}
                for genre in all_genres:
                    if genre:
                        genre_counts[genre] = genre_counts.get(genre, 0) + 1
                
                # Get top genres
                favorite_genres = sorted(
                    genre_counts.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5]
                
                # Count movies this month/year
                now = datetime.now()
                this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                this_year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                
                movies_this_month = collection.count_documents({
                    "user_id": user_id,
                    "watch_date": {"$gte": this_month_start}
                })
                
                movies_this_year = collection.count_documents({
                    "user_id": user_id,
                    "watch_date": {"$gte": this_year_start}
                })
                
                # Find highest/lowest rated movies
                highest_movie = collection.find_one({
                    "user_id": user_id,
                    "rating": stats_data["highest_rated"]
                })
                
                lowest_movie = collection.find_one({
                    "user_id": user_id,
                    "rating": stats_data["lowest_rated"]
                })
                
                return MovieStats(
                    user_id=user_id,
                    total_movies=stats_data.get("total_movies", 0),
                    total_series=stats_data.get("total_series", 0),
                    total_watch_time=stats_data.get("total_watch_time", 0),
                    average_rating=round(stats_data.get("average_rating", 0), 1),
                    favorite_genres=[genre for genre, count in favorite_genres],
                    movies_this_month=movies_this_month,
                    movies_this_year=movies_this_year,
                    highest_rated_movie=highest_movie.get("title") if highest_movie else None,
                    lowest_rated_movie=lowest_movie.get("title") if lowest_movie else None
                )
            else:
                return MovieStats(user_id=user_id)
                
        except Exception as e:
            logger.error(f"Error getting movie stats: {e}")
            return MovieStats(user_id=user_id)
    
    async def _extract_movie_info(self, title: str, is_series: bool) -> Optional[Dict[str, Any]]:
        """Extract movie information using AI"""
        try:
            media_type = "сериал" if is_series else "фильм"
            
            prompt = f"""
Найди информацию о {media_type}: "{title}"

Верни результат в формате JSON:
{{
  "year": год_выпуска,
  "genre": ["жанр1", "жанр2"],
  "director": "режиссер",
  "duration": длительность_в_минутах
}}

Если не можешь найти информацию, верни null для соответствующих полей.
Отвечай ТОЛЬКО JSON без дополнительного текста.
"""
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL_FALLBACK,  # Use cheaper model for this
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
            
            return parse_json_response(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Error extracting movie info: {e}")
            return None
    
    async def _analyze_user_preferences(self, movies: List[MovieEntry]) -> Dict[str, Any]:
        """Analyze user preferences from movie history"""
        try:
            # Calculate preference scores
            genre_scores = {}
            director_scores = {}
            rating_distribution = []
            
            for movie in movies:
                # Weight by rating (higher rated movies count more)
                weight = movie.rating / 10.0
                
                # Count genres
                for genre in movie.genre:
                    if genre:
                        genre_scores[genre] = genre_scores.get(genre, 0) + weight
                
                # Count directors
                if movie.director:
                    director_scores[movie.director] = director_scores.get(movie.director, 0) + weight
                
                rating_distribution.append(movie.rating)
            
            # Get top preferences
            top_genres = sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)[:5]
            top_directors = sorted(director_scores.items(), key=lambda x: x[1], reverse=True)[:3]
            
            avg_rating = sum(rating_distribution) / len(rating_distribution) if rating_distribution else 5.0
            
            return {
                "preferred_genres": [genre for genre, score in top_genres],
                "preferred_directors": [director for director, score in top_directors],
                "average_rating": avg_rating,
                "min_acceptable_rating": max(avg_rating - 1.5, 5.0)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing preferences: {e}")
            return {}
    
    async def _generate_ai_recommendations(
        self, user_movies: List[MovieEntry], preferences: Dict[str, Any], count: int
    ) -> List[MovieRecommendation]:
        """Generate AI-powered recommendations"""
        try:
            # Prepare user movie history for AI
            movie_history = []
            for movie in user_movies[-20:]:  # Last 20 movies
                movie_history.append({
                    "title": movie.title,
                    "year": movie.year,
                    "genre": movie.genre,
                    "director": movie.director,
                    "rating": movie.rating,
                    "is_series": movie.is_series
                })
            
            prompt = f"""
На основе истории просмотров пользователя, порекомендуй {count} фильмов/сериалов.

ИСТОРИЯ ПРОСМОТРОВ:
{json.dumps(movie_history, ensure_ascii=False, indent=2)}

ПРЕДПОЧТЕНИЯ:
- Любимые жанры: {preferences.get('preferred_genres', [])}
- Любимые режиссеры: {preferences.get('preferred_directors', [])}
- Средняя оценка: {preferences.get('average_rating', 5)}

Верни результат в формате JSON:
{{
  "recommendations": [
    {{
      "title": "название",
      "year": год,
      "genre": ["жанр1", "жанр2"],
      "director": "режиссер",
      "description": "краткое описание",
      "reason": "почему рекомендую",
      "confidence": 0.8,
      "is_series": false
    }}
  ]
}}

Требования:
1. Рекомендуй фильмы/сериалы, которых НЕТ в истории
2. Учитывай предпочтения пользователя
3. Объясни, почему рекомендуешь
4. Confidence от 0.1 до 1.0
5. Отвечай ТОЛЬКО JSON
"""
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL_DEFAULT,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.7
            )
            
            ai_response = parse_json_response(response.choices[0].message.content)
            
            if not ai_response or "recommendations" not in ai_response:
                return []
            
            recommendations = []
            for rec_data in ai_response["recommendations"]:
                recommendation = MovieRecommendation(
                    user_id=user_movies[0].user_id if user_movies else 0,
                    title=rec_data.get("title", ""),
                    year=rec_data.get("year"),
                    genre=rec_data.get("genre", []),
                    director=rec_data.get("director"),
                    description=rec_data.get("description", ""),
                    reason=rec_data.get("reason", ""),
                    confidence=rec_data.get("confidence", 0.5),
                    is_series=rec_data.get("is_series", False)
                )
                recommendations.append(recommendation)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating AI recommendations: {e}")
            return []
    
    async def _get_popular_recommendations(self, count: int) -> List[MovieRecommendation]:
        """Get popular recommendations for new users"""
        popular_movies = [
            {
                "title": "Интерстеллар",
                "year": 2014,
                "genre": ["Фантастика", "Драма"],
                "director": "Кристофер Нолан",
                "description": "Эпическая космическая одиссея о спасении человечества",
                "reason": "Один из лучших научно-фантастических фильмов современности",
                "confidence": 0.9,
                "is_series": False
            },
            {
                "title": "Во все тяжкие",
                "year": 2008,
                "genre": ["Драма", "Криминал"],
                "director": "Винс Гиллиган",
                "description": "История превращения учителя химии в наркобарона",
                "reason": "Признан одним из лучших сериалов всех времен",
                "confidence": 0.9,
                "is_series": True
            },
            {
                "title": "Паразиты",
                "year": 2019,
                "genre": ["Триллер", "Комедия", "Драма"],
                "director": "Пон Чжун Хо",
                "description": "Корейский фильм о социальном неравенстве",
                "reason": "Оскароносный фильм с уникальным стилем",
                "confidence": 0.8,
                "is_series": False
            }
        ]
        
        recommendations = []
        for movie_data in popular_movies[:count]:
            recommendation = MovieRecommendation(
                title=movie_data["title"],
                year=movie_data["year"],
                genre=movie_data["genre"],
                director=movie_data["director"],
                description=movie_data["description"],
                reason=movie_data["reason"],
                confidence=movie_data["confidence"],
                is_series=movie_data["is_series"]
            )
            recommendations.append(recommendation)
        
        return recommendations
    
    async def _update_user_stats(self, user_id: int) -> None:
        """Update user statistics after adding a movie"""
        try:
            # This could trigger recalculation of user stats
            # For now, we'll just log it
            logger.info(f"Stats updated for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating user stats: {e}")

class MovieAIService:
    """AI service for movie-related conversations"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.movie_service = MovieExpertService()
    
    async def process_movie_message(self, user_id: int, message: str) -> str:
        """Process movie-related message and potentially save movie"""
        try:
            # Check if user is reporting a watched movie
            if await self._is_movie_report(message):
                movie_info = await self._extract_movie_from_message(message)
                
                if movie_info:
                    # Save the movie
                    success = await self.movie_service.save_movie(
                        user_id=user_id,
                        title=movie_info["title"],
                        rating=movie_info["rating"],
                        review=movie_info.get("review", ""),
                        is_series=movie_info.get("is_series", False)
                    )
                    
                    if success:
                        return f"✅ Фильм '{movie_info['title']}' сохранен с оценкой {movie_info['rating']}/10!"
                    else:
                        return "❌ Не удалось сохранить фильм"
            
            # Check if user is asking for recommendations
            elif await self._is_recommendation_request(message):
                recommendations = await self.movie_service.get_recommendations(user_id, 3)
                
                if recommendations:
                    response = "🎬 **РЕКОМЕНДАЦИИ ДЛЯ ВАС:**\n\n"
                    for i, rec in enumerate(recommendations, 1):
                        media_type = "Сериал" if rec.is_series else "Фильм"
                        response += f"**{i}. {rec.title}** ({rec.year})\n"
                        response += f"📺 {media_type} | {', '.join(rec.genre)}\n"
                        response += f"🎭 Режиссер: {rec.director}\n"
                        response += f"📝 {rec.description}\n"
                        response += f"💡 {rec.reason}\n\n"
                    
                    return response
                else:
                    return "🤷‍♂️ Пока не хватает данных для рекомендаций. Добавьте несколько фильмов!"
            
            # General movie conversation
            else:
                user_movies = await self.movie_service.get_user_movies(user_id, 10)
                return await self._generate_movie_response(message, user_movies)
        
        except Exception as e:
            logger.error(f"Error processing movie message: {e}")
            return "❌ Произошла ошибка при обработке сообщения о фильмах"
    
    async def _is_movie_report(self, message: str) -> bool:
        """Check if message is a movie watching report"""
        movie_indicators = [
            "посмотрел", "посмотрела", "смотрел", "смотрела",
            "оценка", "оценил", "оценила", "/10", "из 10"
        ]
        
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in movie_indicators)
    
    async def _is_recommendation_request(self, message: str) -> bool:
        """Check if message is asking for recommendations"""
        recommendation_indicators = [
            "посоветуй", "рекомендации", "что посмотреть",
            "предложи фильм", "что-нибудь интересное"
        ]
        
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in recommendation_indicators)
    
    async def _extract_movie_from_message(self, message: str) -> Optional[Dict[str, Any]]:
        """Extract movie information from user message"""
        try:
            prompt = f"""
Извлеки информацию о фильме/сериале из сообщения пользователя:
"{message}"

Верни результат в формате JSON:
{{
  "title": "название фильма/сериала",
  "rating": рейтинг_от_1_до_10,
  "review": "отзыв пользователя",
  "is_series": true/false
}}

Если не можешь определить какую-то информацию, используй разумные значения по умолчанию.
Отвечай ТОЛЬКО JSON без дополнительного текста.
"""
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL_FALLBACK,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3
            )
            
            return parse_json_response(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Error extracting movie from message: {e}")
            return None
    
    async def _generate_movie_response(self, message: str, user_movies: List[MovieEntry]) -> str:
        """Generate conversational response about movies"""
        try:
            # Prepare user movie history
            movie_history = []
            for movie in user_movies[-10:]:
                movie_history.append({
                    "title": movie.title,
                    "rating": movie.rating,
                    "genre": movie.genre
                })
            
            prompt = f"""
Пользователь написал: "{message}"

История его просмотров (последние 10):
{json.dumps(movie_history, ensure_ascii=False, indent=2)}

Ответь как эксперт по фильмам, учитывая его предпочтения.
Будь дружелюбным и информативным.
Ответ должен быть не более 500 символов.
"""
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL_DEFAULT,
                messages=[
                    {"role": "system", "content": "Ты эксперт по фильмам и сериалам. Даёшь полезные советы о кино."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating movie response: {e}")
            return "🎬 Интересный вопрос о кино! К сожалению, не могу сейчас дать развернутый ответ."