from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path 


class Settings(BaseSettings):
    # Base de datos
    db_host:     str = "localhost"
    db_port:     int = 5432
    db_user:     str = "tfg_user"
    db_password: str = "tfg_pass"
    db_name:     str = "tfg_finance"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # APIs externas
    tiingo_api_key:  str = ""
    finnhub_api_key: str = ""
    fmp_api_key:     str = ""

    # Indices de riesgo
    risk_index_symbols: str = ""

    # JWT
    jwt_secret_key:        str
    jwt_algorithm:         str = "HS256"
    jwt_expiration_minutes: int = 60  # 60 min

    model_config = SettingsConfigDict(
            env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def db_url_sync(self) -> str:
        """Para Alembic y scripts que no usan async."""
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def risk_index_symbol_list(self) -> list[str]:
        symbols = [s.strip().upper() for s in self.risk_index_symbols.split(",")]
        return [s for s in symbols if s]


settings = Settings()
