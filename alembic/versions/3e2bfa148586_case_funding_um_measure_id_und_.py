"""case_funding um measure_id und foerderfaehige_kosten erweitert

Revision ID: 3e2bfa148586
Revises: d42426091c00
Create Date: 2026-09-21 17:59:51.895405

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e2bfa148586'
down_revision: Union[str, Sequence[str], None] = 'd42426091c00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = 'fk_case_funding_measure_id_measure'


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('case_funding', schema=None) as batch_op:
        batch_op.add_column(sa.Column('measure_id', sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column('foerderfaehige_kosten', sa.Numeric(precision=12, scale=2), nullable=True)
        )
        batch_op.create_foreign_key(FK_NAME, 'measure', ['measure_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('case_funding', schema=None) as batch_op:
        batch_op.drop_constraint(FK_NAME, type_='foreignkey')
        batch_op.drop_column('foerderfaehige_kosten')
        batch_op.drop_column('measure_id')
