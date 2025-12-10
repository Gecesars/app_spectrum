import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate
from celery import Celery

db = SQLAlchemy()
ma = Marshmallow()
migrate = Migrate()


def create_app(config_object=None):
    """Application Factory para Flask."""
    app = Flask(__name__)
    config_path = config_object or os.getenv("FLASK_CONFIG", "config.DevConfig")
    app.config.from_object(config_path)

    register_extensions(app)
    # Importa modelos para povoar o metadata do SQLAlchemy/Alembic.
    from app import models  # noqa: F401
    register_blueprints(app)

    return app


def register_extensions(app: Flask) -> None:
    db.init_app(app)
    ma.init_app(app)
    migrate.init_app(app, db)


def register_blueprints(app: Flask) -> None:
    from app.blueprints.api import api_bp
    from app.blueprints.fm import fm_bp
    from app.blueprints.radcom import radcom_bp
    from app.blueprints.tv import tv_bp
    from app.blueprints.gis import gis_bp
    from app.blueprints.rtr import rtr_bp

    app.register_blueprint(api_bp, url_prefix="/")
    app.register_blueprint(fm_bp, url_prefix="/api/v1/fm")
    app.register_blueprint(radcom_bp, url_prefix="/api/v1/radcom")
    app.register_blueprint(tv_bp, url_prefix="/api/v1/tv")
    app.register_blueprint(gis_bp, url_prefix="/api/v1/gis")
    app.register_blueprint(rtr_bp, url_prefix="/api/v1/rtr")


def make_celery(app: Flask) -> Celery:
    """Cria instância do Celery acoplada ao contexto do Flask."""
    celery = Celery(
        app.import_name,
        broker=app.config.get("CELERY_BROKER_URL"),
        backend=app.config.get("CELERY_RESULT_BACKEND"),
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
