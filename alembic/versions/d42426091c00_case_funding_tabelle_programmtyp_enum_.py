"""case_funding tabelle, programmtyp enum, case regelversion entfernt

Revision ID: d42426091c00
Revises: aacc318fd480
Create Date: 2026-09-21 12:26:39.100269

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd42426091c00'
down_revision: Union[str, Sequence[str], None] = 'aacc318fd480'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PROGRAMMTYP = sa.Enum('KFW_458', 'BEG_EM', name='programmtyp', native_enum=False)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('case_funding',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('programm', PROGRAMMTYP, nullable=False),
    sa.Column('foerderbetrag', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('regelversion', sa.String(length=30), nullable=False),
    sa.Column('regel_hash', sa.String(length=64), nullable=False),
    sa.Column('berechnet_am', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['case.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'programm')
    )

    # SQLite kennt kein natives ALTER COLUMN - batch_alter_table baut die
    # Tabelle im Hintergrund neu (Standard-Workaround fuer SQLite in Alembic).
    with op.batch_alter_table('case', schema=None) as batch_op:
        batch_op.drop_column('regelversion')
        batch_op.drop_column('regel_hash')

    with op.batch_alter_table('funding_history', schema=None) as batch_op:
        batch_op.alter_column(
            'programm',
            existing_type=sa.VARCHAR(length=50),
            type_=PROGRAMMTYP,
            existing_nullable=False,
        )
        batch_op.create_unique_constraint(
            'uq_funding_history_building_jahr_programm', ['building_id', 'jahr', 'programm']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('funding_history', schema=None) as batch_op:
        batch_op.drop_constraint('uq_funding_history_building_jahr_programm', type_='unique')
        batch_op.alter_column(
            'programm',
            existing_type=PROGRAMMTYP,
            type_=sa.VARCHAR(length=50),
            existing_nullable=False,
        )

    with op.batch_alter_table('case', schema=None) as batch_op:
        batch_op.add_column(sa.Column('regel_hash', sa.VARCHAR(length=64), nullable=True))
        batch_op.add_column(sa.Column('regelversion', sa.VARCHAR(length=30), nullable=True))

    op.drop_table('case_funding')
