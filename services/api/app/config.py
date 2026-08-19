from pydantic_settings import BaseSettings, SettingsConfigDict

from app.paths import API_DIR, REPO_ROOT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), str(API_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "智讯通 API"
    debug: bool = True
    demo_mode: bool = True
    scheduler_enabled: bool = False
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 1440
    database_url: str = "sqlite:///./zhixuntong.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    crawler_mode: str = "mock"
    rag_mode: str = "mock"
    dify_mode: str = "mock"
    notify_mode: str = "log"

    crawler_base_url: str = "http://127.0.0.1:8001"
    rag_base_url: str = "http://127.0.0.1:9380"
    dify_base_url: str = "http://127.0.0.1:80"
    dify_api_key: str = ""
    dingtalk_webhook: str = ""
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    smtp_from: str = "zhixuntong@example.com"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
