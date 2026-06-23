from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_url: str = "postgresql://cqrs_user:cqrs_pass@localhost:5432/cqrs_db"
    redis_url: str = "redis://localhost:6379"
    es_url: str = "http://localhost:9200"
    es_index: str = "products"
    stream_key: str = "ecommerce_events"
    stream_group: str = "projector_group"
    stream_consumer: str = "projector_1"

    class Config:
        env_file = ".env"


settings = Settings()
