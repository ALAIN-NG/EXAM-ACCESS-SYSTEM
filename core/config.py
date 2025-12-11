# core/config.py
import os
from decouple import config, Csv
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Django Core
DEBUG = config('DEBUG', default=True, cast=bool)
SECRET_KEY = config('SECRET_KEY', default='dev-secret-key-change-me')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Database
DB_ENGINE = config('DB_ENGINE', default='django.db.backends.sqlite3')
DB_NAME = config('DB_NAME', default=BASE_DIR / 'db.sqlite3')
DB_USER = config('DB_USER', default='')
DB_PASSWORD = config('DB_PASSWORD', default='')
DB_HOST = config('DB_HOST', default='')
DB_PORT = config('DB_PORT', default='')

# CORS
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000', cast=Csv())
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000')

# Email
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@examen-system.edu')

# Storage
USE_S3 = config('USE_S3', default=False, cast=bool)
if USE_S3:
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')

# Cache
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

# Application specific
QR_CODE_VALIDITY = config('QR_CODE_VALIDITY', default=30, cast=int)  # minutes
EXAM_START_TOLERANCE = config('EXAM_START_TOLERANCE', default=30, cast=int)
EXAM_END_TOLERANCE = config('EXAM_END_TOLERANCE', default=30, cast=int)
MAX_EXPORT_ROWS = config('MAX_EXPORT_ROWS', default=10000, cast=int)

# Notifications
ENABLE_EMAIL_NOTIFICATIONS = config('ENABLE_EMAIL_NOTIFICATIONS', default=False, cast=bool)
ENABLE_SMS_NOTIFICATIONS = config('ENABLE_SMS_NOTIFICATIONS', default=False, cast=bool)
SEND_SCAN_CONFIRMATION = config('SEND_SCAN_CONFIRMATION', default=True, cast=bool)

# Logging
LOG_LEVEL = config('LOG_LEVEL', default='INFO')
LOG_TO_FILE = config('LOG_TO_FILE', default=True, cast=bool)
LOG_MAX_SIZE = config('LOG_MAX_SIZE', default=10, cast=int)  # MB
LOG_BACKUP_COUNT = config('LOG_BACKUP_COUNT', default=5, cast=int)

# Rate limiting
SCAN_RATE_LIMIT = config('SCAN_RATE_LIMIT', default='50/minute')
API_RATE_LIMIT_USER = config('API_RATE_LIMIT_USER', default='1000/hour')
API_RATE_LIMIT_ANON = config('API_RATE_LIMIT_ANON', default='100/day')

# JWT
JWT_ACCESS_TOKEN_LIFETIME = config('JWT_ACCESS_TOKEN_LIFETIME', default=1, cast=int)  # hours
JWT_REFRESH_TOKEN_LIFETIME = config('JWT_REFRESH_TOKEN_LIFETIME', default=24, cast=int)  # hours

# Third-party integrations
SENTRY_DSN = config('SENTRY_DSN', default='')
TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_PHONE_NUMBER = config('TWILIO_PHONE_NUMBER', default='')


def get_database_config():
    """Retourne la configuration de la base de données"""
    if DB_ENGINE == 'django.db.backends.sqlite3':
        return {
            'ENGINE': DB_ENGINE,
            'NAME': str(DB_NAME),
        }
    else:
        return {
            'ENGINE': DB_ENGINE,
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
        }


def get_email_config():
    """Retourne la configuration email"""
    return {
        'BACKEND': EMAIL_BACKEND,
        'HOST': EMAIL_HOST,
        'PORT': EMAIL_PORT,
        'USE_TLS': EMAIL_USE_TLS,
        'USER': EMAIL_HOST_USER,
        'PASSWORD': EMAIL_HOST_PASSWORD,
        'DEFAULT_FROM_EMAIL': DEFAULT_FROM_EMAIL,
    }


def get_application_settings():
    """Retourne les paramètres spécifiques à l'application"""
    return {
        'QR_CODE_VALIDITY_MINUTES': QR_CODE_VALIDITY,
        'EXAM_START_TOLERANCE_MINUTES': EXAM_START_TOLERANCE,
        'EXAM_END_TOLERANCE_MINUTES': EXAM_END_TOLERANCE,
        'MAX_EXPORT_ROWS': MAX_EXPORT_ROWS,
        'ENABLE_EMAIL_NOTIFICATIONS': ENABLE_EMAIL_NOTIFICATIONS,
        'ENABLE_SMS_NOTIFICATIONS': ENABLE_SMS_NOTIFICATIONS,
        'SEND_SCAN_CONFIRMATION': SEND_SCAN_CONFIRMATION,
    }