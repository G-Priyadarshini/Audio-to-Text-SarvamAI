from urllib.parse import quote_plus
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MySQL
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "Priya@1108"
    MYSQL_DB: str = "icepot"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Sarvam AI
    SARVAM_API_KEY: str = ""
    SARVAM_MODEL: str = "saaras:v3"
    # Optional path to ffmpeg executable. If set, this will be used by pydub.
    FFMPEG_BINARY: str = ""

    # Groq LLM
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Sarvam Job-based API
    SARVAM_JOB_API_BASE: str = "https://api.sarvam.ai/speech-to-text-translate/job/v1"
    SARVAM_BLOB_BASE_URL: str = "https://appsprodpublicsa.blob.core.windows.net/bulk-upload-storage"
    SARVAM_POLL_INTERVAL_INITIAL: int = 5       # seconds
    SARVAM_POLL_MAX_BACKOFF: int = 60            # seconds
    SARVAM_POLL_TIMEOUT: int = 7200              # 2 hours max

    # Sarvam direct API limit: 30 s per request — use 25 s chunks for safety
    SARVAM_MAX_CHUNK_SECONDS: int = 25

    # Limits
    MAX_FILE_SIZE_MB: int = 500
    MAX_DURATION_SECONDS: int = 7200
    MAX_CHUNK_SIZE_MB: int = 5
    TEMP_DIR: str = "./tmp/uploads"

    # Rate Limiting
    RATE_LIMIT_JOBS_PER_MINUTE: int = 10
    RATE_LIMIT_CHUNKS_PER_MINUTE: int = 100
    MAX_CONCURRENT_JOBS_PER_IP: int = 5

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    # Development fallback: when true the app will use a local SQLite DB
    USE_SQLITE: bool = False
    # Set to True to use arq worker for transcription instead of inline processing
    USE_ARQ_WORKER: bool = False

    @property
    def DATABASE_URL(self) -> str:
        if self.USE_SQLITE:
            return f"sqlite+aiosqlite:///./tmp/icepot_dev.db"
        pwd = quote_plus(self.MYSQL_PASSWORD)
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{pwd}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
        )

    @property
    def SYNC_DATABASE_URL(self) -> str:
        if self.USE_SQLITE:
            return f"sqlite:///./tmp/icepot_dev.db"
        pwd = quote_plus(self.MYSQL_PASSWORD)
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{pwd}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
        )

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def MAX_CHUNK_SIZE_BYTES(self) -> int:
        return self.MAX_CHUNK_SIZE_MB * 1024 * 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
