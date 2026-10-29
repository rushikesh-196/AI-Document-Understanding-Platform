"""
Centralized Configuration for Intelligent OCR Backend
"""

import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'intelligent-ocr-secret-key-2026')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    EXTRACTED_FOLDER = os.path.join(BASE_DIR, 'extracted')
    OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')  # Backward compatibility
    
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max limit
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf', 'tiff', 'bmp', 'webp'}
    ALLOWED_MIME_TYPES = {
        'image/jpeg', 'image/png', 'image/tiff', 'image/bmp', 'image/webp',
        'application/pdf', 'application/x-pdf'
    }
    
    # Engine & NLP Settings
    PADDLE_LANG = 'en'
    SPACY_MODEL = 'en_core_web_sm'
    
    # Cache settings
    ENABLE_CACHE = True

    # MySQL is used only by services/auth_service.py for the users table.
    MYSQL_HOST = os.environ.get('MYSQL_HOST', "localhost")
    MYSQL_USER = os.environ.get('MYSQL_USER', "root")
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', "Devaroot@123")
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', "intelligent_ocr")
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', "3306"))
