from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = Field(
        default="https://us.cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_BASE_URL", "LANGFUSE_HOST"),
    )
    langfuse_project_url: str = Field(
        default="https://us.cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_PROJECT_URL", "LANGFUSE_BASE_URL", "LANGFUSE_HOST"),
    )

    shodan_api_key: str = ""
    hibp_api_key: str = ""
    github_token: str = ""
    nvd_api_key: str = ""

    target_ips: str = "8.8.8.8,1.1.1.1,93.184.216.34"
    demo_domains: str = "example.com,acme-corp.test,contoso.test"

    clickhouse_host: str = "ycvc8ozito.us-west-2.aws.clickhouse.cloud"
    clickhouse_port: int = 8443
    clickhouse_database: str = Field(default="default", validation_alias=AliasChoices("CLICKHOUSE_DB", "CLICKHOUSE_DATABASE"))
    clickhouse_user: str = "default"
    clickhouse_password: str = ".GTexzm1mE8z5"
    clickhouse_secure: bool = True
    frontend_origin: str = "http://localhost:5173"
    agent_interval_minutes: int = Field(default=5, ge=1)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def target_ip_list(self) -> list[str]:
        return [item.strip() for item in self.target_ips.split(",") if item.strip()]

    @property
    def demo_domain_list(self) -> list[str]:
        return [item.strip() for item in self.demo_domains.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
