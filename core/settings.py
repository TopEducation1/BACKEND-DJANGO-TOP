import os
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

import pymysql
pymysql.install_as_MySQLdb()

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = str(os.getenv('SECRET_KEY'))

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv(
    "DEBUG",
    "False"
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

ALLOWED_HOSTS = [
    'backend-django-top-production.up.railway.app',
    '127.0.0.1',
    'localhost',
    'localhost:8000',
    'app.top.education'
]

# ============================================================
# MX HELP DESK / COLOMBIA
# ============================================================

MX_HELP_DESK_BASE_URL = os.getenv(
    "MX_HELP_DESK_BASE_URL",
    "https://api-dev.universidad.top"
).rstrip("/")

MX_HELP_DESK_SERVICE_TOKEN = os.getenv(
    "MX_HELP_DESK_SERVICE_TOKEN",
    ""
).strip()

MX_HELP_DESK_CONNECT_TIMEOUT = int(
    os.getenv(
        "MX_HELP_DESK_CONNECT_TIMEOUT",
        "10"
    )
)

MX_HELP_DESK_READ_TIMEOUT = int(
    os.getenv(
        "MX_HELP_DESK_READ_TIMEOUT",
        "45"
    )
)

# Configuración de seguridad HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

SECURE_SSL_REDIRECT = False

MX_B2C_ACCESS_EVENT_URL = os.getenv("MX_B2C_ACCESS_EVENT_URL", "")
MX_B2C_ACCESS_EVENT_HMAC_SECRET = os.getenv("MX_B2C_ACCESS_EVENT_HMAC_SECRET", "").strip()
MX_B2C_SUBSCRIPTION_MANAGEMENT_URL = os.getenv(
    "MX_B2C_SUBSCRIPTION_MANAGEMENT_URL",
    "https://top.education/account?tab=license",
)
MX_B2C_COLOMBIA_ACCOUNT_URL = os.getenv(
    "MX_B2C_COLOMBIA_ACCOUNT_URL",
    "https://top.education/account",
)
MX_B2C_TIMEOUT = int(os.getenv("MX_B2C_TIMEOUT", "60"))
MX_B2C_CONNECT_TIMEOUT = int(os.getenv("MX_B2C_CONNECT_TIMEOUT", "10"))

STRIPE_BILLING_PORTAL_RETURN_URL = os.getenv(
    "STRIPE_BILLING_PORTAL_RETURN_URL",
    "https://top.education/account?tab=license",
)

MX_STRIPE_B2C_WEBHOOK_URL = os.getenv("MX_STRIPE_B2C_WEBHOOK_URL")
STRIPE_B2C_WEBHOOK_SECRET = os.getenv("STRIPE_B2C_WEBHOOK_SECRET")
MX_WEBHOOK_TIMEOUT = int(os.getenv("MX_WEBHOOK_TIMEOUT", "10"))

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "") 
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")    # whsec_...

STRIPE_PRICE_YEARLY = os.getenv("STRIPE_PRICE_YEARLY", "")
STRIPE_PRICE_MONTHLY = os.getenv("STRIPE_PRICE_MONTHLY", "")

STRIPE_PRICE_BASIC_MONTHLY = os.getenv("STRIPE_PRICE_BASIC_MONTHLY", default=None)
STRIPE_PRICE_BASIC_YEARLY = os.getenv("STRIPE_PRICE_BASIC_YEARLY", default=None)

STRIPE_PRICE_X_MONTHLY = os.getenv("STRIPE_PRICE_X_MONTHLY", default=None)
STRIPE_PRICE_X_YEARLY = os.getenv("STRIPE_PRICE_X_YEARLY", default=None)

STRIPE_PRICE_PLUS_MONTHLY = os.getenv("STRIPE_PRICE_PLUS_MONTHLY", default=None)
STRIPE_PRICE_PLUS_YEARLY = os.getenv("STRIPE_PRICE_PLUS_YEARLY", default=None)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

STRIPE_SUCCESS_URL = os.getenv(
    "STRIPE_SUCCESS_URL",
    f"{FRONTEND_URL}/success?session_id={{CHECKOUT_SESSION_ID}}"
)

STRIPE_CANCEL_URL = os.getenv(
    "STRIPE_CANCEL_URL",
    f"{FRONTEND_URL}/cancel"
)

APPEND_SLASH = True

COURSES_EXTERNAL_ENDPOINT = os.getenv(
    "COURSES_EXTERNAL_ENDPOINT",
    "https://api-colombia.universidad.top"
).rstrip("/")

# API Key
COURSES_EXTERNAL_API_KEY = os.getenv(
    "COURSES_EXTERNAL_API_KEY",
    os.getenv("AWS_COURSES_API_KEY", "")
)

COURSES_EXTERNAL_AUTH_HEADER = "x-api-key"

# Host derivado automáticamente desde la URL
COURSES_EXTERNAL_HOST = urlparse(
    COURSES_EXTERNAL_ENDPOINT
).netloc

# Hosts permitidos para el proxy
COURSES_EXTERNAL_ALLOWED_HOSTS = [
    COURSES_EXTERNAL_HOST,
]

# Compatibilidad con el proxy actual
PROXY_WHITELIST = {
    COURSES_EXTERNAL_HOST,
}

PROXY_HEADERS = {
    COURSES_EXTERNAL_HOST: {
        COURSES_EXTERNAL_AUTH_HEADER: COURSES_EXTERNAL_API_KEY,
        "Accept": "application/json",
    }
}

PROXY_TIMEOUT = int(os.getenv("PROXY_TIMEOUT", "180"))

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'rest_framework',
    'topeducation',
    'corsheaders',
    'ckeditor',
    'ckeditor_uploader',
    'django_select2',
]   

MIDDLEWARE = [
    # CORS debe quedar arriba para poder agregar los headers
    # también a respuestas generadas por otros middlewares.
    'corsheaders.middleware.CorsMiddleware',

    # Seguridad
    'django.middleware.security.SecurityMiddleware',

    # Compresión de respuestas grandes:
    # JSON de skills, universidades, certificaciones, etc.
    'django.middleware.gzip.GZipMiddleware',

    # WhiteNoise solo si decides volver a servir estáticos desde Django.
    'whitenoise.middleware.WhiteNoiseMiddleware',

    # Sesiones
    'django.contrib.sessions.middleware.SessionMiddleware',

    # CommonMiddleware
    'django.middleware.common.CommonMiddleware',

    # CSRF
    'django.middleware.csrf.CsrfViewMiddleware',

    # Autenticación
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    # Mensajes
    'django.contrib.messages.middleware.MessageMiddleware',

    # Protección clickjacking
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",

    "https://top.education",
    "https://www.top.education",
    "https://app.top.education",

    "https://frontend-react-top-production.up.railway.app",
]

CV_ANALYSIS_URL = os.getenv(
    "CV_ANALYSIS_URL",
    "https://api-colombia.universidad.top/v2/cv/analysis"
)

CV_ANALYSIS_TIMEOUT = int(os.getenv("CV_ANALYSIS_TIMEOUT", "120"))

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:3001',
    'https://backend-django-top-production.up.railway.app',
    'https://frontend-react-top-production.up.railway.app',
    'https://top.education',
    'https://www.top.education',
    'http://localhost:45678',
    
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]


# Configuración de cookies seguras

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SESSION_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SAMESITE = "None"

# El resto de tu configuración permanece igual
ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# ============================================================
# DATABASE
# ============================================================

DB_CONN_MAX_AGE = int(
    os.getenv(
        "DB_CONN_MAX_AGE",
        "0"
    )
)

DB_CONN_HEALTH_CHECKS = os.getenv(
    "DB_CONN_HEALTH_CHECKS",
    "True"
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

DB_CONNECT_TIMEOUT = int(
    os.getenv(
        "DB_CONNECT_TIMEOUT",
        "15"
    )
)

DB_READ_TIMEOUT = int(
    os.getenv(
        "DB_READ_TIMEOUT",
        "60"
    )
)

DB_WRITE_TIMEOUT = int(
    os.getenv(
        "DB_WRITE_TIMEOUT",
        "60"
    )
)


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",

        "NAME": (
            os.getenv("MYSQL_DATABASE")
            or os.getenv("MYSQLDATABASE")
        ),

        "USER": (
            os.getenv("MYSQLUSER")
            or os.getenv("MYSQL_USER")
        ),

        "PASSWORD": (
            os.getenv("MYSQLPASSWORD")
            or os.getenv("MYSQL_PASSWORD")
        ),

        "HOST": (
            os.getenv("DATABASE_HOST")
            or os.getenv("MYSQLHOST")
        ),

        "PORT": (
            os.getenv("MYSQLPORT")
            or "3306"
        ),

        # ----------------------------------------------------
        # CONEXIONES
        # ----------------------------------------------------

        "CONN_MAX_AGE": DB_CONN_MAX_AGE,

        "CONN_HEALTH_CHECKS": DB_CONN_HEALTH_CHECKS,

        # ----------------------------------------------------
        # MYSQL / PYMYSQL
        # ----------------------------------------------------

        "OPTIONS": {
            "charset": "utf8mb4",

            "connect_timeout":
                DB_CONNECT_TIMEOUT,

            "read_timeout":
                DB_READ_TIMEOUT,

            "write_timeout":
                DB_WRITE_TIMEOUT,
        },
    }
}

# ============================================================
# LOGGING
# ============================================================

DJANGO_LOG_LEVEL = os.getenv(
    "DJANGO_LOG_LEVEL",
    "INFO"
).upper()

DJANGO_DB_LOG_LEVEL = os.getenv(
    "DJANGO_DB_LOG_LEVEL",
    "WARNING"
).upper()


LOGGING = {
    "version": 1,

    "disable_existing_loggers": False,

    "formatters": {
        "verbose": {
            "format": (
                "[{asctime}] "
                "{levelname} "
                "{name}: "
                "{message}"
            ),
            "style": "{",
        },
    },

    "handlers": {
        "console": {
            "class":
                "logging.StreamHandler",

            "formatter":
                "verbose",
        },
    },

    "loggers": {

        # Errores HTTP / views
        "django.request": {
            "handlers": [
                "console"
            ],

            "level":
                "ERROR",

            "propagate":
                False,
        },

        # Errores del servidor de desarrollo
        "django.server": {
            "handlers": [
                "console"
            ],

            "level":
                "INFO",

            "propagate":
                False,
        },

        # MySQL
        "django.db.backends": {
            "handlers": [
                "console"
            ],

            "level":
                DJANGO_DB_LOG_LEVEL,

            "propagate":
                False,
        },
    },
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# ============================================================
# MEDIA FILES
# ============================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = os.getenv(
    "MEDIA_ROOT",
    os.getenv(
        "RAILWAY_VOLUME_MOUNT_PATH",
        os.path.join(BASE_DIR, "media"),
    ),
)

CKEDITOR_UPLOAD_PATH = "uploads/"

#STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"  # 👈 default seguro
)

# ⚠️ SOLO define SMTP si NO estás usando console backend
if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
