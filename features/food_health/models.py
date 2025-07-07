"""Models for food and health tracking"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from core.utils import generate_uuid, get_current_timestamp

@dataclass
class NutritionData:
    """Nutrition information for food items"""
    calories: float
    protein: float  # grams
    carbs: float    # grams
    fat: float      # grams
    fiber: Optional[float] = None  # grams
    sugar: Optional[float] = None  # grams
    sodium: Optional[float] = None  # mg
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'calories': self.calories,
            'protein': self.protein,
            'carbs': self.carbs,
            'fat': self.fat,
            'fiber': self.fiber,
            'sugar': self.sugar,
            'sodium': self.sodium
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NutritionData':
        return cls(
            calories=data.get('calories', 0),
            protein=data.get('protein', 0),
            carbs=data.get('carbs', 0),
            fat=data.get('fat', 0),
            fiber=data.get('fiber'),
            sugar=data.get('sugar'),
            sodium=data.get('sodium')
        )

@dataclass
class FoodItem:
    """Individual food item with analysis"""
    id: str = field(default_factory=generate_uuid)
    name: str = ""
    description: str = ""
    portion_size: float = 100.0  # grams
    nutrition: Optional[NutritionData] = None
    confidence: float = 0.0  # AI confidence score
    image_base64: Optional[str] = None
    created_at: datetime = field(default_factory=get_current_timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'portion_size': self.portion_size,
            'nutrition': self.nutrition.to_dict() if self.nutrition else None,
            'confidence': self.confidence,
            'image_base64': self.image_base64,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FoodItem':
        nutrition = None
        if data.get('nutrition'):
            nutrition = NutritionData.from_dict(data['nutrition'])
        
        return cls(
            id=data.get('id', generate_uuid()),
            name=data.get('name', ''),
            description=data.get('description', ''),
            portion_size=data.get('portion_size', 100.0),
            nutrition=nutrition,
            confidence=data.get('confidence', 0.0),
            image_base64=data.get('image_base64'),
            created_at=data.get('created_at', get_current_timestamp())
        )

@dataclass
class FoodAnalysis:
    """Complete food analysis for a user"""
    id: str = field(default_factory=generate_uuid)
    user_id: int = 0
    chat_id: int = 0
    message_id: int = 0
    food_items: List[FoodItem] = field(default_factory=list)
    total_nutrition: Optional[NutritionData] = None
    analysis_timestamp: datetime = field(default_factory=get_current_timestamp)
    ai_model_used: str = "gpt-4o"
    processing_time: float = 0.0  # seconds
    
    def calculate_total_nutrition(self) -> NutritionData:
        """Calculate total nutrition from all food items"""
        total_calories = sum(item.nutrition.calories if item.nutrition else 0 for item in self.food_items)
        total_protein = sum(item.nutrition.protein if item.nutrition else 0 for item in self.food_items)
        total_carbs = sum(item.nutrition.carbs if item.nutrition else 0 for item in self.food_items)
        total_fat = sum(item.nutrition.fat if item.nutrition else 0 for item in self.food_items)
        
        return NutritionData(
            calories=total_calories,
            protein=total_protein,
            carbs=total_carbs,
            fat=total_fat
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'chat_id': self.chat_id,
            'message_id': self.message_id,
            'food_items': [item.to_dict() for item in self.food_items],
            'total_nutrition': self.total_nutrition.to_dict() if self.total_nutrition else None,
            'analysis_timestamp': self.analysis_timestamp,
            'ai_model_used': self.ai_model_used,
            'processing_time': self.processing_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FoodAnalysis':
        food_items = []
        for item_data in data.get('food_items', []):
            food_items.append(FoodItem.from_dict(item_data))
        
        total_nutrition = None
        if data.get('total_nutrition'):
            total_nutrition = NutritionData.from_dict(data['total_nutrition'])
        
        return cls(
            id=data.get('id', generate_uuid()),
            user_id=data.get('user_id', 0),
            chat_id=data.get('chat_id', 0),
            message_id=data.get('message_id', 0),
            food_items=food_items,
            total_nutrition=total_nutrition,
            analysis_timestamp=data.get('analysis_timestamp', get_current_timestamp()),
            ai_model_used=data.get('ai_model_used', 'gpt-4o'),
            processing_time=data.get('processing_time', 0.0)
        )

@dataclass
class HealthProfile:
    """User health profile"""
    user_id: int = 0
    age: Optional[int] = None
    gender: Optional[str] = None  # male/female/other
    height: Optional[float] = None  # cm
    weight: Optional[float] = None  # kg
    activity_level: str = "moderate"  # sedentary/light/moderate/active/very_active
    fitness_goal: str = "maintain"  # lose/maintain/gain
    dietary_restrictions: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)
    daily_calorie_goal: Optional[float] = None
    daily_protein_goal: Optional[float] = None
    daily_carb_goal: Optional[float] = None
    daily_fat_goal: Optional[float] = None
    created_at: datetime = field(default_factory=get_current_timestamp)
    updated_at: datetime = field(default_factory=get_current_timestamp)
    
    def calculate_bmr(self) -> Optional[float]:
        """Calculate Basal Metabolic Rate using Harris-Benedict equation"""
        if not all([self.age, self.height, self.weight, self.gender]):
            return None
        
        if self.gender == "male":
            return 88.362 + (13.397 * self.weight) + (4.799 * self.height) - (5.677 * self.age)
        elif self.gender == "female":
            return 447.593 + (9.247 * self.weight) + (3.098 * self.height) - (4.330 * self.age)
        else:
            # Use average for other genders
            male_bmr = 88.362 + (13.397 * self.weight) + (4.799 * self.height) - (5.677 * self.age)
            female_bmr = 447.593 + (9.247 * self.weight) + (3.098 * self.height) - (4.330 * self.age)
            return (male_bmr + female_bmr) / 2
    
    def calculate_tdee(self) -> Optional[float]:
        """Calculate Total Daily Energy Expenditure"""
        bmr = self.calculate_bmr()
        if not bmr:
            return None
        
        activity_multipliers = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9
        }
        
        multiplier = activity_multipliers.get(self.activity_level, 1.55)
        return bmr * multiplier
    
    def calculate_daily_goals(self) -> Dict[str, float]:
        """Calculate daily nutrition goals"""
        tdee = self.calculate_tdee()
        if not tdee:
            return {}
        
        # Adjust calories based on fitness goal
        if self.fitness_goal == "lose":
            daily_calories = tdee * 0.8  # 20% deficit
        elif self.fitness_goal == "gain":
            daily_calories = tdee * 1.2  # 20% surplus
        else:
            daily_calories = tdee  # maintain
        
        # Calculate macronutrient goals (standard ratios)
        protein_calories = daily_calories * 0.25  # 25% protein
        carb_calories = daily_calories * 0.45     # 45% carbs
        fat_calories = daily_calories * 0.30      # 30% fat
        
        return {
            "calories": daily_calories,
            "protein": protein_calories / 4,  # 4 calories per gram
            "carbs": carb_calories / 4,       # 4 calories per gram
            "fat": fat_calories / 9           # 9 calories per gram
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'age': self.age,
            'gender': self.gender,
            'height': self.height,
            'weight': self.weight,
            'activity_level': self.activity_level,
            'fitness_goal': self.fitness_goal,
            'dietary_restrictions': self.dietary_restrictions,
            'allergies': self.allergies,
            'daily_calorie_goal': self.daily_calorie_goal,
            'daily_protein_goal': self.daily_protein_goal,
            'daily_carb_goal': self.daily_carb_goal,
            'daily_fat_goal': self.daily_fat_goal,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HealthProfile':
        return cls(
            user_id=data.get('user_id', 0),
            age=data.get('age'),
            gender=data.get('gender'),
            height=data.get('height'),
            weight=data.get('weight'),
            activity_level=data.get('activity_level', 'moderate'),
            fitness_goal=data.get('fitness_goal', 'maintain'),
            dietary_restrictions=data.get('dietary_restrictions', []),
            allergies=data.get('allergies', []),
            daily_calorie_goal=data.get('daily_calorie_goal'),
            daily_protein_goal=data.get('daily_protein_goal'),
            daily_carb_goal=data.get('daily_carb_goal'),
            daily_fat_goal=data.get('daily_fat_goal'),
            created_at=data.get('created_at', get_current_timestamp()),
            updated_at=data.get('updated_at', get_current_timestamp())
        )

@dataclass
class WorkoutSession:
    """Individual workout session"""
    id: str = field(default_factory=generate_uuid)
    user_id: int = 0
    activity_type: str = ""  # running, cycling, strength, etc.
    duration: float = 0.0  # minutes
    calories_burned: float = 0.0
    intensity: int = 5  # 1-10 scale
    notes: str = ""
    timestamp: datetime = field(default_factory=get_current_timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'activity_type': self.activity_type,
            'duration': self.duration,
            'calories_burned': self.calories_burned,
            'intensity': self.intensity,
            'notes': self.notes,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkoutSession':
        return cls(
            id=data.get('id', generate_uuid()),
            user_id=data.get('user_id', 0),
            activity_type=data.get('activity_type', ''),
            duration=data.get('duration', 0.0),
            calories_burned=data.get('calories_burned', 0.0),
            intensity=data.get('intensity', 5),
            notes=data.get('notes', ''),
            timestamp=data.get('timestamp', get_current_timestamp())
        )

@dataclass
class StepsData:
    """Daily steps tracking"""
    id: str = field(default_factory=generate_uuid)
    user_id: int = 0
    date: datetime = field(default_factory=lambda: get_current_timestamp().replace(hour=0, minute=0, second=0, microsecond=0))
    steps: int = 0
    distance: Optional[float] = None  # km
    calories_burned: Optional[float] = None
    active_minutes: Optional[int] = None
    timestamp: datetime = field(default_factory=get_current_timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'date': self.date,
            'steps': self.steps,
            'distance': self.distance,
            'calories_burned': self.calories_burned,
            'active_minutes': self.active_minutes,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StepsData':
        return cls(
            id=data.get('id', generate_uuid()),
            user_id=data.get('user_id', 0),
            date=data.get('date', get_current_timestamp().replace(hour=0, minute=0, second=0, microsecond=0)),
            steps=data.get('steps', 0),
            distance=data.get('distance'),
            calories_burned=data.get('calories_burned'),
            active_minutes=data.get('active_minutes'),
            timestamp=data.get('timestamp', get_current_timestamp())
        )