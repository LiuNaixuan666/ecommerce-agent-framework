import os


# Keep the test suite deterministic and isolated from locally running services.
# These values are applied before pytest imports application modules.
os.environ["SESSION_STORAGE"] = "memory"
os.environ["INGESTION_STORAGE"] = "memory"
os.environ["STORAGE_BACKEND"] = "memory"
os.environ["LLM_PROVIDER"] = "local"
os.environ["EMBEDDING_PROVIDER"] = "local"
os.environ["POSTGRES_HOST"] = "127.0.0.1"
os.environ["POSTGRES_PORT"] = "1"
os.environ["REDIS_HOST"] = "127.0.0.1"
os.environ["REDIS_PORT"] = "1"
