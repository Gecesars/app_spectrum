"""Add metadata columns for FM/TV stations."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_add_metadata_columns"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("estacoes_fm", sa.Column("id_plano", sa.String(length=32), nullable=True))
    op.add_column("estacoes_fm", sa.Column("uf", sa.String(length=2), nullable=True))
    op.add_column("estacoes_fm", sa.Column("cod_municipio", sa.String(length=16), nullable=True))
    op.add_column("estacoes_fm", sa.Column("municipio", sa.String(length=128), nullable=True))
    op.add_column("estacoes_fm", sa.Column("freq_mhz", sa.Float(), nullable=True))
    op.add_column("estacoes_fm", sa.Column("status", sa.String(length=32), nullable=True))
    op.add_column("estacoes_fm", sa.Column("entidade", sa.String(length=255), nullable=True))
    op.add_column("estacoes_fm", sa.Column("cnpj", sa.String(length=32), nullable=True))
    op.add_column("estacoes_fm", sa.Column("carater", sa.String(length=8), nullable=True))
    op.add_column("estacoes_fm", sa.Column("finalidade", sa.String(length=32), nullable=True))
    op.add_column("estacoes_fm", sa.Column("fistel", sa.String(length=64), nullable=True))
    op.add_column("estacoes_fm", sa.Column("observacoes", sa.Text(), nullable=True))

    op.add_column("estacoes_tv", sa.Column("id_plano", sa.String(length=32), nullable=True))
    op.add_column("estacoes_tv", sa.Column("uf", sa.String(length=2), nullable=True))
    op.add_column("estacoes_tv", sa.Column("cod_municipio", sa.String(length=16), nullable=True))
    op.add_column("estacoes_tv", sa.Column("municipio", sa.String(length=128), nullable=True))
    op.add_column("estacoes_tv", sa.Column("freq_mhz", sa.Float(), nullable=True))
    op.add_column("estacoes_tv", sa.Column("status", sa.String(length=32), nullable=True))
    op.add_column("estacoes_tv", sa.Column("entidade", sa.String(length=255), nullable=True))
    op.add_column("estacoes_tv", sa.Column("cnpj", sa.String(length=32), nullable=True))
    op.add_column("estacoes_tv", sa.Column("carater", sa.String(length=8), nullable=True))
    op.add_column("estacoes_tv", sa.Column("finalidade", sa.String(length=32), nullable=True))
    op.add_column("estacoes_tv", sa.Column("fistel", sa.String(length=64), nullable=True))
    op.add_column("estacoes_tv", sa.Column("fistel_geradora", sa.String(length=64), nullable=True))
    op.add_column("estacoes_tv", sa.Column("observacoes", sa.Text(), nullable=True))
