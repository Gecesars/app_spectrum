"""Change setores geom to generic geometry."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_setores_geom_generic"
down_revision = "0002_add_metadata_columns"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE setores_censitarios ALTER COLUMN geom TYPE geometry(Geometry, 4674) USING geom"
    )


def downgrade():
    op.execute(
        "ALTER TABLE setores_censitarios ALTER COLUMN geom TYPE geometry(MultiPolygon, 4674) USING ST_Multi(geom)"
    )
