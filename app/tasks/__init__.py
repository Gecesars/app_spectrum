from celery import shared_task


@shared_task(name="app.tasks.demo.add")
def add(x: float, y: float) -> float:
    """Tarefa de soma para validar a infraestrutura Celery."""
    return x + y


@shared_task(name="app.tasks.demo.ping")
def ping() -> str:
    """Retorna string simples para teste de fila."""
    return "pong"
