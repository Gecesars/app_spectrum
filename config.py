import os


class BaseConfig:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///espectro.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
    JSON_SORT_KEYS = False
    PROPAGATION_DEFAULT_SRID = 4674  # SIRGAS 2000
    PROPAGATION_SAMPLE_POINTS = 72  # radiais de 5 em 5°
    PROPAGATION_RASTER_TABLE = os.getenv("PROPAGATION_RASTER_TABLE", "srtm_raster")
    PROPAGATION_RASTER_COLUMN = os.getenv("PROPAGATION_RASTER_COLUMN", "rast")
    # Mapzen/Skadi (Viewfinderpanoramas) tiles em .hgt.gz
    SRTM_BASE_URL = os.getenv(
        "SRTM_BASE_URL", "https://s3.amazonaws.com/elevation-tiles-prod/skadi"
    )
    SRTM_DOWNLOAD_DIR = os.getenv("SRTM_DOWNLOAD_DIR", "data/srtm")


class DevConfig(BaseConfig):
    DEBUG = True


class ProdConfig(BaseConfig):
    DEBUG = False


class TestConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
