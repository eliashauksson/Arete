from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    strava_client_id: str = ""
    strava_client_secret: str = ""
    database_url: str = "sqlite:///./arete.db"
    strava_route_export_path: str = "./data/routes"


settings = Settings()
