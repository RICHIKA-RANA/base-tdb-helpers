import os
from dotenv import load_dotenv
from talkingdb.models.api.mode import ClientMode

load_dotenv()

CLIENT_MODE = os.getenv("CLIENT_MODE", ClientMode.DIRECT)
CE_HOST = os.getenv("CE_HOST", None)


ALLOWED_EXTENSIONS = {"docx"}
MAX_FILE_SIZE_MB = int(os.getenv("TDB_MAX_FILE_SIZE_MB", "50"))
TDB_API_KEY = os.getenv("TDB_API_KEY")


class Config:
    CLIENT_MODE: ClientMode = CLIENT_MODE
    API_TIMEOUT = 300
    CE_HOST = CE_HOST
    ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS
    MAX_FILE_SIZE_MB = MAX_FILE_SIZE_MB
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    TDB_API_KEY = TDB_API_KEY


config = Config()
