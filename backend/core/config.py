import os

class Settings:
    # DB URLs
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/sentraflow")
    WAREHOUSE_URL: str = os.getenv("WAREHOUSE_URL", "postgresql://postgres:postgres@localhost:5432/sentraflow")
    
    # Redis Cache URL
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Kafka / Redpanda Brokers
    KAFKA_BROKERS: str = os.getenv("KAFKA_BROKERS", "localhost:9092")
    
    # S3 / MinIO Configuration
    S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", "http://localhost:9000")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "sentraflow-lake")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
    
    # Microservices
    ML_SERVICE_URL: str = os.getenv("ML_SERVICE_URL", "http://localhost:8001")
    
    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "supersecretjwtkeyforlocaldevelopment1234567890")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

settings = Settings()
