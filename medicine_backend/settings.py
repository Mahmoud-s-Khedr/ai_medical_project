from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    CORS_ALLOW_ALL_ORIGINS=(bool, True),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-only-medicine-ocr-secret-key")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "medicine_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "medicine_backend.wsgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Cairo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Upload limits (global multipart guards) ───────────────────────────────────
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int("DATA_UPLOAD_MAX_MEMORY_SIZE", default=8 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = env.int("FILE_UPLOAD_MAX_MEMORY_SIZE", default=8 * 1024 * 1024)

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOWED_ORIGINS = [origin for origin in CORS_ALLOWED_ORIGINS if origin.strip() != "*"]
CORS_ALLOW_ALL_ORIGINS = env("CORS_ALLOW_ALL_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# ── REST Framework ─────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "api.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/hour",
        "user": "1000/day",
        "auth": "10/hour",
    },
}

PASSWORD_RESET_TIMEOUT = 86400  # 24 hours

# ── Simple JWT ─────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "UPDATE_LAST_LOGIN": True,
}

# ── drf-spectacular (Swagger / OpenAPI) ────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "Medicine OCR API",
    "DESCRIPTION": (
        "REST API for medicine lookup via OCR image scanning, "
        "medication reminders, and fuzzy search against a medicine database."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ── Email ──────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@medicine-ocr.com")
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

# ── OCR / AI settings ─────────────────────────────────────────────────────────
FUZZY_BACKEND = "rapidfuzz"
OCR_MAX_CANDIDATES = env.int("OCR_MAX_CANDIDATES", default=5)
OCR_MIN_SCORE = env.float("OCR_MIN_SCORE", default=0.55)
OCR_RESULT_FLOOR = env.float("OCR_RESULT_FLOOR", default=0.60)
OCR_LOW_CONFIDENCE_THRESHOLD = env.float("OCR_LOW_CONFIDENCE_THRESHOLD", default=0.72)
OCR_HIGH_CONFIDENCE_THRESHOLD = env.float("OCR_HIGH_CONFIDENCE_THRESHOLD", default=0.85)
OCR_LOW_CONFIDENCE_MAX_RESULTS = env.int("OCR_LOW_CONFIDENCE_MAX_RESULTS", default=2)
OCR_MEDICINE_NAME_FIELD = "trade_name"
YOLO_MODEL_PATH = str(BASE_DIR / "drug_detector.pt")
OCR_MAX_UPLOAD_BYTES = env.int("OCR_MAX_UPLOAD_BYTES", default=8 * 1024 * 1024)
OCR_MEDICINE_CACHE_TTL_SECONDS = env.int("OCR_MEDICINE_CACHE_TTL_SECONDS", default=300)
OCR_ROTATION_ANGLES = env("OCR_ROTATION_ANGLES", default="0,-10,10,-20,20")
OCR_EARLY_EXIT_CONFIDENCE = env.float("OCR_EARLY_EXIT_CONFIDENCE", default=0.90)
OCR_SKIP_TESSERACT_IF_EASYOCR_CONFIDENT = env.float("OCR_SKIP_TESSERACT_IF_EASYOCR_CONFIDENT", default=0.88)
OCR_USE_TESSERACT = env.bool("OCR_USE_TESSERACT", default=False)
OCR_MIN_TOKEN_LENGTH = env.int("OCR_MIN_TOKEN_LENGTH", default=3)
OCR_TOKEN_STOPWORDS = env(
    "OCR_TOKEN_STOPWORDS",
    default="a,an,and,at,by,for,from,in,of,on,or,the,to,with",
)
OCR_PHRASE_STRONG_SCORE = env.float("OCR_PHRASE_STRONG_SCORE", default=0.85)
OCR_INCLUDE_MATCH_DEBUG = env.bool("OCR_INCLUDE_MATCH_DEBUG", default=True)
SEARCH_COMBINED_TOP_K = env.int("SEARCH_COMBINED_TOP_K", default=200)
SEARCH_FUZZY_MIN_SCORE = env.float("SEARCH_FUZZY_MIN_SCORE", default=0.45)
SEARCH_FULLTEXT_WEIGHT = env.float("SEARCH_FULLTEXT_WEIGHT", default=0.60)
SEARCH_FUZZY_WEIGHT = env.float("SEARCH_FUZZY_WEIGHT", default=0.40)
SEARCH_CANDIDATE_EXPANSION = env.int("SEARCH_CANDIDATE_EXPANSION", default=4)
SEARCH_MEDICINE_CACHE_TTL_SECONDS = env.int("SEARCH_MEDICINE_CACHE_TTL_SECONDS", default=300)
SEARCH_LENGTH_PENALTY_ENABLED = env.bool("SEARCH_LENGTH_PENALTY_ENABLED", default=True)
SEARCH_LENGTH_PENALTY_STRENGTH = env.float("SEARCH_LENGTH_PENALTY_STRENGTH", default=2.2)
SEARCH_LENGTH_RATIO_FLOOR = env.float("SEARCH_LENGTH_RATIO_FLOOR", default=0.35)
SEARCH_ALIAS_BOOST_WEIGHT = env.float("SEARCH_ALIAS_BOOST_WEIGHT", default=0.10)
SEARCH_INGREDIENT_BOOST_WEIGHT = env.float("SEARCH_INGREDIENT_BOOST_WEIGHT", default=0.10)
SEARCH_COVERAGE_BOOST_WEIGHT = env.float("SEARCH_COVERAGE_BOOST_WEIGHT", default=0.06)
SEARCH_DRUG_CLASS_PENALTY_WEIGHT = env.float("SEARCH_DRUG_CLASS_PENALTY_WEIGHT", default=0.05)
