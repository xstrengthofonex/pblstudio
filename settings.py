import os

PORT = os.getenv("PORT", 4321)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(ROOT_DIR, "static")
TEMPLATES_DIR = os.path.join(ROOT_DIR, "templates")
DB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "heroku_q9nc1d4v"
