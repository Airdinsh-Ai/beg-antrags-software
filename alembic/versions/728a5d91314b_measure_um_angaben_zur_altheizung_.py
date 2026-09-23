"""measure um Angaben zur Altheizung erweitert

Die Heizung, die ein Waermeerzeuger ersetzt - Voraussetzung fuer den
Klimageschwindigkeitsbonus (KfW-Merkblatt 458, Stand 07/2026). Alle drei Spalten
nullable: Pflicht erst bei der KfW-458-Berechnung fuer Selbstnutzer.

Revision ID: 728a5d91314b
Revises: 991380b86083
Create Date: 2026-09-23 17:23:19.051643

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '728a5d91314b'
down_revision: Union[str, Sequence[str], None] = '991380b86083'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ALTHEIZUNG_ART = sa.Enum(
    'OEL', 'KOHLE', 'GAS_ETAGE', 'NACHTSPEICHER', 'GAS', 'BIOMASSE', 'SONSTIGE',
    name='altheizungart',
    native_enum=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('measure', schema=None) as batch_op:
        batch_op.add_column(sa.Column('alte_heizung_art', ALTHEIZUNG_ART, nullable=True))
        batch_op.add_column(sa.Column('alte_heizung_inbetriebnahme', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('alte_heizung_funktionstuechtig', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('measure', schema=None) as batch_op:
        batch_op.drop_column('alte_heizung_funktionstuechtig')
        batch_op.drop_column('alte_heizung_inbetriebnahme')
        batch_op.drop_column('alte_heizung_art')
