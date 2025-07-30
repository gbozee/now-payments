from starlette.config import Config
from starlette.datastructures import Secret, URL

config = Config(".env")
DEBUG = config("DEBUG", cast=bool, default=True)
PAYMENT_SHEET = config("PAYMENT_SHEET")
NOW_SHEET_SERVICE = config("NOW_SHEET_SERVICE")
HOST_URL = config("HOST_URL", default="http://localhost:8000")