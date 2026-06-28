
from pathlib import Path
from decouple import config  # Add this import

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = config('SECRET_KEY', default='django-insecure-1$z(p2@rl_0&xl!x7juluk$4+&d#b4sz7$f%w!6uy7**kv4di*')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = []

# Google Maps API Key
GOOGLE_MAPS_API_KEY = config('GOOGLE_MAPS_API_KEY', default='AIzaSyBt7MFCWjtXTDZq07PZBa_4V953Xy9GYmM')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'parking',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'parking_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'parking' / 'templates',  # ✅ App-level templates
            BASE_DIR / 'templates',               # ✅ Project-level templates (optional)
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'parking.context_processors.google_maps_key',  # Add this line
            ],
        },
    },
]

WSGI_APPLICATION = 'parking_system.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}



AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]



LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'  # Changed to Indian timezone

USE_I18N = True

USE_TZ = True



STATIC_URL = '/static/'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login Settings
LOGIN_URL = 'user_login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'user_login'
import os

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
# ==================== EMAIL CONFIGURATION ====================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = '✉️ ajitilage@gmail.com'
EMAIL_HOST_PASSWORD = 'zkwiwytceevusjum'  # Your actual app password
DEFAULT_FROM_EMAIL = 'Parkease <✉️ ajitilage@gmail.com>'
SERVER_EMAIL = '✉️ ajitilage@gmail.com'

# ==================== LOGGING ====================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
        'file': {'class': 'logging.FileHandler', 'filename': 'debug.log'},
    },
    'root': {'handlers': ['console', 'file'], 'level': 'INFO'},
}