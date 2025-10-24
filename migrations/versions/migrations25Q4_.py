""""
Migrations for the 2025 Q4 Authenticator release
"""

from alembic import op
import psycopg2
import sqlalchemy as sa
from tapisservice.config import conf
from tapisservice.logs import get_logger
logger = get_logger(__name__)


# revision identifiers, used by Alembic.
revision = '25Q4'
down_revision = '1.3.4'
branch_labels = None
depends_on = None


def upgrade():
    logger.info("Starting 25Q4 upgrade")
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('client_id', sa.String(length=80), nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('always_allow', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    logger.info("Ending 25Q4 upgrade")


def downgrade():
    op.drop_table('users')

