from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    cxai_access_token: str = Field(
        default="",
        alias="CXAI_PLAYGROUND_ACCESS_TOKEN",
        validation_alias="CXAI_PLAYGROUND_ACCESS_TOKEN",
    )
    openai_base_url: str = Field(default="https://cxai-playground.cisco.com")
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    llm_model: str = Field(default="gpt-4o-mini")
    chroma_persist_dir: str = Field(default="./chroma_db")
    chroma_collection: str = Field(default="bems_tickets")
    top_k: int = Field(default=5)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)


settings = Settings()
