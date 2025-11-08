import os
from dotenv import load_dotenv

# Charge les variables d'environnement depuis .env
load_dotenv()

# Chemin absolu du projet
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # 🔐 Clé secrète (pour les sessions, les formulaires, etc.)
    SECRET_KEY = os.getenv("SECRET_KEY", "escoget1985-@#%Z!9T8z$L0rQ1pF3bC5sA7xN")

    # 📦 Base de données SQLite locale ou autre (PostgreSQL possible sur Render)
    DB_PATH = os.getenv("DB_PATH", "db.sqlite3")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",  # Render/PostgreSQL
        f"sqlite:///{os.path.join(BASE_DIR, DB_PATH)}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 📁 Dossier des uploads (images candidats, etc.)
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 Mo max par fichier

    # ⚙️ Détermine automatiquement le mode (dev ou prod)
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = FLASK_ENV == "development"

    # 🔒 Sécurité renforcée pour la prod
    SESSION_COOKIE_SECURE = FLASK_ENV == "production"
    REMEMBER_COOKIE_SECURE = FLASK_ENV == "production"
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_PROTECTION = "strong"

    # 💡 Optionnel : permet à Flask de faire confiance aux proxys Render
    PREFERRED_URL_SCHEME = "https"

    # 🧠 Mode clair dans la console (utile pour savoir où tu es)
    @staticmethod
    def init_app(app):
        mode = os.getenv("FLASK_ENV", "production").upper()
        print(f"🚀 ESCOGET - Mode {mode} activé")
