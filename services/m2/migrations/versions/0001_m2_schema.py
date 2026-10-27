"""M2 namespace baseline; no application or approval business tables."""

from alembic import op
from sqlalchemy.schema import CreateSchema

revision = "0001_m2_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(CreateSchema("m2", if_not_exists=True))


def downgrade():
    # Retain the namespace and Alembic table at base. Never CASCADE user tables.
    pass
