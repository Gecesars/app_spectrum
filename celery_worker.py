from app import create_app, make_celery

flask_app = create_app()
celery = make_celery(flask_app)

# Garante descoberta de tarefas dentro de app.tasks
celery.autodiscover_tasks(["app.tasks"])


@celery.task(name="app.tasks.healthcheck")
def healthcheck() -> str:
    """Tarefa simples para validar se o worker está ativo."""
    return "ok"


if __name__ == "__main__":
    celery.start()
