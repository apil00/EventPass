from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure--z2nv#3kxhqv+7&*v*35zhbfny!4$e@hc#^!x4l3s+(q**f^q0'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    'jazzmin',
    'django_ckeditor_5',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # custom app
    'core',
    'users',
    'events',
    'rest_framework',
    'drf_yasg',
    'recognition',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'users.middleware.FaceRegistrationMiddleware',
]

ROOT_URLCONF = 'EventPass.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'users.context_processors.user_notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'EventPass.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'eventpass_db',
        'USER': 'postgres',
        'PASSWORD': 'Apil12345',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

TIME_ZONE = 'Asia/Kathmandu' 


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'users.CustomUser'

# eSewa Payment Settings (TEST MODE)
ESEWA_MERCHANT_ID = 'EPAYTEST'
ESEWA_SUCCESS_URL = 'https://127.0.0.1:8000/payment/success/'
ESEWA_FAILURE_URL = 'https://127.0.0.1:8000/payment/failure/'
ESEWA_API_URL = 'https://rc-epay.esewa.com.np/api/epay/main/v2/form'

JAZZMIN_SETTINGS = {
    "site_title": "EventPass Admin",
    "site_header": "EventPass Administration",
    "site_brand": "EventPass",
    "welcome_sign": "Welcome to the EventPass Admin Panel",

    "copyright": "EventPass",

    "topmenu_links": [
        {"name": "Home",  "url": "/", "permissions": ["auth.view_user"]},
        {"model": "users.customuser"},
        {"app": "events"},
    ],

    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],

    "order_with_respect_to": ["events", "tickets","users"],

    "icons": {
        "auth": "fas fa-users-cog",
        "users.customuser": "fas fa-user",
        "events.event": "fas fa-calendar-alt",
        "tickets.ticket": "fas fa-ticket-alt",
    },

    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
}


CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': ['heading', '|', 'bold', 'italic', 'link',
                    'bulletedList', 'numberedList', 'blockQuote'],
    },
    'extends': {
        'blockToolbar': [
            'paragraph', 'heading1', 'heading2', 'heading3',
            '|',
            'bulletedList', 'numberedList',
            '|',
            'blockQuote',
        ],
        'toolbar': ['heading', '|', 'outdent', 'indent', '|', 'bold', 'italic', 
                   'link', 'underline', 'strikethrough',
                   'code','subscript', 'superscript', 'highlight', '|', 
                   'bulletedList', 'numberedList', 'todoList', '|',
                   'blockQuote', 'insertImage', '|',
                   'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor', 
                   'mediaEmbed', 'removeFormat', 'insertTable'],
        'image': {
            'toolbar': ['imageTextAlternative', '|', 'imageStyle:alignLeft',
                        'imageStyle:alignRight', 'imageStyle:alignCenter', 
                        'imageStyle:side', '|'],
            'styles': [
                'full',
                'side',
                'alignLeft',
                'alignRight',
                'alignCenter',
            ]
        }
    }
}

SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    },
    'USE_SESSION_AUTH': False,
}

# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# DEFAULT_FROM_EMAIL = 'noreply@yourdomain.com'

# Email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'sandbox.smtp.mailtrap.io'  # e.g., smtp.gmail.com
EMAIL_PORT = 2525
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'e20e76135c371f'
EMAIL_HOST_PASSWORD = 'f6ca0647e3f66c'

SITE_URL = 'http://127.0.0.1:8000'