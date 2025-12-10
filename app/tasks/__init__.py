from celery import shared_task
from app import db
from app.models import Simulacao
from app.tasks.fm import gerar_contorno_fm, avaliar_viabilidade_fm  # noqa: F401
from app.tasks.tv import gerar_contorno_tv  # noqa: F401


@shared_task(name="app.tasks.demo.add")
def add(x: float, y: float) -> float:
    """Tarefa de soma para validar a infraestrutura Celery."""
    return x + y


@shared_task(name="app.tasks.demo.ping")
def ping() -> str:
    """Retorna string simples para teste de fila."""
    return "pong"


@shared_task(name="app.tasks.radcom.viabilidade")
def radcom_viabilidade(sim_id: str, params: dict | None = None) -> dict:
    """
    Stub de viabilidade RadCom.
    Atualiza a simulação com status 'done' e mensagem indicativa.
    """
    sim = Simulacao.query.get(sim_id)
    if not sim:
        return {"status": "error", "detail": "simulação não encontrada"}

    sim.status = "done"
    sim.mensagem_status = "Avaliação RadCom stub (implementar cálculo de contorno 91 dBµV/m e compatibilidade)."
    db.session.commit()

    return {"status": sim.status, "mensagem": sim.mensagem_status, "sim_id": sim.id}
