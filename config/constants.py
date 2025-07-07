"""Application constants"""

# Admin user IDs
ADMIN_IDS = [139373848]  # Dimidiy

# Chat types
CHAT_TYPE_PRIVATE = "private"
CHAT_TYPE_GROUP = "group"
CHAT_TYPE_SUPERGROUP = "supergroup"

# Message types
MESSAGE_TYPE_TEXT = "text"
MESSAGE_TYPE_PHOTO = "photo"
MESSAGE_TYPE_DOCUMENT = "document"
MESSAGE_TYPE_VOICE = "voice"

# Food analysis constants
FOOD_ANALYSIS_TIMEOUT = 30  # seconds
MAX_FOOD_ITEMS_PER_REQUEST = 10
DEFAULT_PORTION_SIZE = 100  # grams

# Movie constants
MOVIE_RATING_MIN = 1
MOVIE_RATING_MAX = 10
MAX_MOVIE_RECOMMENDATIONS = 5

# Health constants
MIN_AGE = 10
MAX_AGE = 120
MIN_HEIGHT = 50  # cm
MAX_HEIGHT = 250  # cm
MIN_WEIGHT = 20  # kg
MAX_WEIGHT = 300  # kg
MAX_STEPS_PER_DAY = 100000

# Message management constants
AUTO_DELETE_TIMEOUT_MIN = 30  # seconds
AUTO_DELETE_TIMEOUT_MAX = 600  # seconds (10 minutes)
AUTO_DELETE_TIMEOUT_DEFAULT = 300  # seconds (5 minutes)

# Cache constants
CACHE_KEY_USER_PROFILE = "user_profile_{user_id}"
CACHE_KEY_FOOD_STATS = "food_stats_{user_id}_{period}"
CACHE_KEY_MOVIE_RECOMMENDATIONS = "movie_recs_{user_id}"

# Collection names
COLLECTION_USERS = "users"
COLLECTION_FOOD_ANALYSIS = "food_analysis"
COLLECTION_MOVIES = "movies"
COLLECTION_HEALTH_PROFILES = "health_profiles"
COLLECTION_WORKOUTS = "workouts"
COLLECTION_STEPS = "steps"
COLLECTION_TOPIC_SETTINGS = "topic_settings"
COLLECTION_USER_STATES = "user_states"

# Bot states
STATE_WAITING_FOOD_INPUT = "waiting_food_input"
STATE_WAITING_MOVIE_INPUT = "waiting_movie_input"
STATE_WAITING_HEALTH_INPUT = "waiting_health_input"
STATE_WAITING_WORKOUT_INPUT = "waiting_workout_input"
STATE_WAITING_STEPS_INPUT = "waiting_steps_input"

# Nutrition constants
CALORIES_PER_GRAM_PROTEIN = 4
CALORIES_PER_GRAM_CARBS = 4
CALORIES_PER_GRAM_FAT = 9

# OpenAI Vision constants
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB
SUPPORTED_IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.webp', '.gif']