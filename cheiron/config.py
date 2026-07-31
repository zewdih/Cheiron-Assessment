from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openai_api_key: str
    openai_model_primary: str = "gpt-4.1"
    openai_model_narration: str = "gpt-4.1-mini"
    ct_api_base_url: str = "https://clinicaltrials.gov/api/v2/studies"
    max_page_size: int = 1000
    max_total_results: int = 5000
    rate_limit_rpm: int = 30
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()