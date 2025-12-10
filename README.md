# Sistema de Engenharia de Espectro

Aplicação Flask + PostGIS + Celery que implementa a base para os módulos normativos de FM, RadCom e TV Digital descritos no `codex.md`. Este repositório entrega o bootstrap completo (serviços, fábrica de app, tarefa Celery de teste e camada API inicial) e a estrutura para evoluir conforme o roteiro.

## Serviços cobertos
- FM / RTR (primário).
- RadCom (secundário, 25 W).
- TV/RTV analógica e digital (GTVD/RTVD).

## Stack
- Backend: Flask (Application Factory), SQLAlchemy/GeoAlchemy2, Marshmallow, Flask-Migrate.
- Banco: PostgreSQL + PostGIS.
- Fila: Celery.
- Broker/cache: Redis.
- GIS: GDAL/Rasterio (planejado).
- Tiles: pg_tileserv (a partir do PostGIS).
- Frontend: React + Leaflet/MapLibre (pasta `frontend/` reservada).

## Subir em desenvolvimento
1. Crie um arquivo `.env` (opcional) ou exporte as variáveis: `DATABASE_URL`, `REDIS_URL`, `FLASK_ENV`, `FLASK_DEBUG`.
2. Na raiz `espectro_app/`, execute:
   ```bash
   docker-compose up --build
   ```
3. Testes rápidos:
   - API: `curl http://localhost:5000/health` ⇒ `{"status":"ok"}`
   - Celery: `docker-compose exec worker celery -A celery_worker.celery call app.tasks.demo.add --args='[1,2]'`
4. Migrations:
   - `docker-compose exec web flask db upgrade` aplica a estrutura inicial (tabelas normativas, estações, simulações/resultados).
5. Carga de planos básicos (XML em `data/`):
   - Copie os XMLs (plano_basicoTVFM, secudariosTVFM, solicitacoesTVFM) para `data/`.
   - Rode: `docker-compose exec web python -m app.utils.etl.load_tvfm_xml`
   - O ETL trunca e recarrega FM/TV, marcando TV digital via heurística (SBTVD/status) e armazenando diagrama `PadraoAntena_dBd` em `erp_por_radial` (lista de floats).
6. Carga de setores censitários IBGE:
  - Coloque `BR_setores_CD2022.*` em `data/`.
  - Rode: `docker-compose exec web python -m app.utils.etl.load_setores_ibge` (leva alguns minutos; 468k setores).
  - Distribua a população municipal proporcional à área dos setores (usando Censo 2022 municipal):  
    `docker-compose exec web python -m app.utils.etl.distribute_pop_municipal`  
    (usa `data/CD2022_Populacao_Coletada_Imputada_e_Total_Municipio_e_UF_20231222.xlsx`).
7. Normas:
   - Os DOCX originais estão em `data/normas/` (requisitos técnicos). Para extrair CSVs padronizados, rode `docker-compose exec web python -m app.utils.etl.extract_normas_docx` (gera CSVs em `data/normas/` conforme README).
   - Depois, carregue no banco: `docker-compose exec web python -m app.utils.etl.load_normas`.
   - Se não houver CSV de RadCom, o loader insere o padrão (25 W, raio 1 km, altura 30 m).
8. Contornos (P.1546 tabulado):
   - FM/TV usam as curvas oficiais do arquivo `data/Tabulated field strength values P1546.xls` via `app/utils/propagacao/p1546_curves.py`.
   - Endpoints de viabilidade aceitam parâmetros opcionais `time_percent` (50/10/1) e `path` (Land/Sea/Warm Sea/Cold Sea) para ajustar o cálculo.
   - Contornos podem ser obtidos em `GET /simulacoes/<id>/contornos` ou `GET /contornos/<id>`.
9. Raster SRTM (altura efetiva por radial):
  - Fonte default: bucket público Mapzen/Skadi (`https://s3.amazonaws.com/elevation-tiles-prod/skadi`, tiles `.hgt.gz`).
  - Configure env `PROPAGATION_RASTER_TABLE` (default `srtm_raster`) e `PROPAGATION_RASTER_COLUMN` (default `rast`).
  - Para baixar um tile e carregar no PostGIS:  
    `docker-compose exec web python -m app.utils.etl.srtm_downloader --lat <lat> --lon <lon> --load`
  - Para pré-baixar todos os tiles das estações FM/TV já cadastradas (download local, opcional load no PostGIS):  
    `docker-compose exec web python -m app.utils.etl.prefetch_srtm_tiles` (adicione `--load` para carregar em raster).
   - Ajuste `SRTM_BASE_URL`/`SRTM_DOWNLOAD_DIR` via env se quiser outro repositório.

## Estrutura
- `app/` — código Flask.
  - `blueprints/` — API e módulos de domínio (`api`, `fm`, `radcom`, `tv`, `gis`, `rtr`).
  - `tasks/` — tarefas Celery (contornos, interferência, população; inclui tarefa de teste).
  - `models/` — modelos SQLAlchemy/GeoAlchemy2.
  - `utils/` — utilitários de propagação (P.1546, P.526/Assis), normas e ETL.
- `migrations/` — Alembic (inicializado posteriormente).
- `frontend/` — SPA React (placeholder).
- `docker-compose.yml` — orquestra os serviços web, worker, db, redis, pg_tileserv.
- `celery_worker.py` — inicialização do worker Celery.
- `config.py` — configs (dev/prod/test).
- Rotas úteis:  
  - `/contornos/<id>/stats` — área (km²) e população estimada pela interseção com setores IBGE (requer `pop_total` preenchido via `distribute_pop_municipal`).

## Compatibilidade de versão
- Backend agora pinado para Python 3.13 (`Dockerfile` usa `python:3.13-slim` e `requirements.txt` refletem versões compatíveis). Se rodar localmente com outra versão, alinhe as dependências manualmente ou use o contêiner.

## Próximos passos (conforme `codex.md`)
- Criar modelos e migrations das tabelas normativas e de estações.
- Implementar ETLs (PBFM, PRRadCom, PBTV/PBTVD, IBGE).
- Adicionar módulos de propagação (P.1546/P.526) e lógicas normativas por serviço.
- Expor tiles via pg_tileserv e construir o frontend React com mapas e painéis.
