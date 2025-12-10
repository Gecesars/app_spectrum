"""Initial normative and core tables."""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "normas_fm_classes",
        sa.Column("classe", sa.String(length=4), nullable=False),
        sa.Column("erp_max_kw", sa.Float(), nullable=False),
        sa.Column("hnmt_max_m", sa.Float(), nullable=False),
        sa.Column("dist_max_contorno66_km", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("classe"),
    )
    op.create_table(
        "normas_fm_protecao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tipo_interferencia", sa.String(length=32), nullable=False),
        sa.Column("delta_f_khz", sa.Integer(), nullable=True),
        sa.Column("ci_requerida_db", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "normas_fm_radcom_distancias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("classe_fm", sa.String(length=4), nullable=False),
        sa.Column("situacao", sa.String(length=32), nullable=False),
        sa.Column("dist_min_km", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "normas_radcom",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("erp_max_w", sa.Float(), nullable=False),
        sa.Column("raio_servico_km", sa.Float(), nullable=False),
        sa.Column("altura_max_m", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "normas_tv_analogica_classes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("classe", sa.String(length=16), nullable=False),
        sa.Column("faixa_canal", sa.String(length=32), nullable=False),
        sa.Column("erp_max_kw", sa.Float(), nullable=False),
        sa.Column("hnmt_ref_m", sa.Float(), nullable=False),
        sa.Column("dist_max_contorno_protegido_km", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "normas_tv_digital_classes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("classe", sa.String(length=16), nullable=False),
        sa.Column("faixa_canal", sa.String(length=32), nullable=False),
        sa.Column("erp_max_kw", sa.Float(), nullable=False),
        sa.Column("hnmt_ref_m", sa.Float(), nullable=False),
        sa.Column("dist_max_contorno_protegido_km", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "normas_tv_fm_compatibilidade",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("canal_tv", sa.Integer(), nullable=False),
        sa.Column("faixa_canais_fm", sa.String(length=64), nullable=False),
        sa.Column("tipo_interferencia", sa.String(length=32), nullable=False),
        sa.Column("ci_requerida_db", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "normas_tv_nivel_contorno",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tecnologia", sa.String(length=16), nullable=False),
        sa.Column("faixa_canal", sa.String(length=32), nullable=False),
        sa.Column("nivel_campo_dbuv_m", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "normas_tv_protecao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tipo_interferencia", sa.String(length=32), nullable=False),
        sa.Column("tecnologia_desejado", sa.String(length=16), nullable=False),
        sa.Column("tecnologia_interferente", sa.String(length=16), nullable=False),
        sa.Column("delta_canal", sa.String(length=8), nullable=True),
        sa.Column("ci_requerida_db", sa.Float(), nullable=False),
        sa.Column("observacao", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "setores_censitarios",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("municipio", sa.String(length=128), nullable=False),
        sa.Column("tipo", sa.String(length=16), nullable=False),
        sa.Column("pop_total", sa.Integer(), nullable=True),
        sa.Column("geom", Geometry(geometry_type="MULTIPOLYGON", srid=4674), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "simulacoes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tipo", sa.String(length=32), nullable=False),
        sa.Column("params", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("mensagem_status", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "estacoes_fm",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("id_mosaico", sa.String(length=64), nullable=True),
        sa.Column("servico", sa.String(length=8), nullable=False),
        sa.Column("canal", sa.Integer(), nullable=False),
        sa.Column("classe", sa.String(length=4), nullable=True),
        sa.Column("erp_max_kw", sa.Float(), nullable=True),
        sa.Column("hnmt_m", sa.Float(), nullable=True),
        sa.Column("erp_por_radial", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4674), nullable=True),
        sa.Column("antena_id", sa.Integer(), nullable=True),
        sa.Column("categoria", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "estacoes_radcom",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("municipio_outorga", sa.String(length=128), nullable=False),
        sa.Column("canal", sa.Integer(), nullable=False),
        sa.Column("erp_w", sa.Float(), nullable=False),
        sa.Column("altura_sistema_m", sa.Float(), nullable=False),
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4674), nullable=True),
        sa.Column("area_prestacao", Geometry(geometry_type="POLYGON", srid=4674), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "estacoes_tv",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("servico", sa.String(length=16), nullable=False),
        sa.Column("tecnologia", sa.String(length=16), nullable=False),
        sa.Column("canal", sa.Integer(), nullable=False),
        sa.Column("classe", sa.String(length=16), nullable=True),
        sa.Column("erp_max_kw", sa.Float(), nullable=True),
        sa.Column("hnmt_m", sa.Float(), nullable=True),
        sa.Column("erp_por_radial", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4674), nullable=True),
        sa.Column("categoria", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "resultados_cobertura",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("simulacao_id", sa.String(length=36), nullable=False),
        sa.Column("tipo_contorno", sa.String(length=64), nullable=False),
        sa.Column("nivel_campo_dbuv_m", sa.Float(), nullable=True),
        sa.Column("geom", Geometry(geometry_type="POLYGON", srid=4674), nullable=False),
        sa.ForeignKeyConstraint(
            ["simulacao_id"],
            ["simulacoes.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_resultados_cobertura_simulacao", "resultados_cobertura", ["simulacao_id"]
    )


def downgrade():
    op.drop_index("idx_resultados_cobertura_simulacao", table_name="resultados_cobertura")
    op.drop_table("resultados_cobertura")
    op.drop_table("estacoes_tv")
    op.drop_table("estacoes_radcom")
    op.drop_table("estacoes_fm")
    op.drop_table("simulacoes")
    op.drop_table("setores_censitarios")
    op.drop_table("normas_tv_protecao")
    op.drop_table("normas_tv_nivel_contorno")
    op.drop_table("normas_tv_fm_compatibilidade")
    op.drop_table("normas_tv_digital_classes")
    op.drop_table("normas_tv_analogica_classes")
    op.drop_table("normas_radcom")
    op.drop_table("normas_fm_radcom_distancias")
    op.drop_table("normas_fm_protecao")
    op.drop_table("normas_fm_classes")
