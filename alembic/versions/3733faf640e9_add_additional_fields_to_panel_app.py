"""Add additional fields to panel app

Revision ID: 3733faf640e9
Revises: 416eb615ff1a
Create Date: 2017-07-25 08:43:56.445034

"""


# revision identifiers, used by Alembic.
revision = '3733faf640e9'
down_revision = '416eb615ff1a'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table
import sideboard.lib.sa
from uber.config import c

try:
    is_sqlite = op.get_context().dialect.name == 'sqlite'
except:
    is_sqlite = False

if is_sqlite:
    op.get_context().connection.execute('PRAGMA foreign_keys=ON;')
    utcnow_server_default = "(datetime('now', 'utc'))"
else:
    utcnow_server_default = "timezone('utc', current_timestamp)"

panel_app_helper = table(
        'panel_application',
        sa.Column('id', sideboard.lib.sa.UUID(), nullable=False),
        sa.Column('length', sa.Unicode()),
        sa.Column('length_text', sa.Unicode()),
        sa.Column('length_reason', sa.Unicode())
        # Other columns not needed
    )

def upgrade():
    op.add_column('panel_application', sa.Column('cost_desc', sa.Unicode(), server_default='', nullable=False))
    op.add_column('panel_application', sa.Column('extra_info', sa.Unicode(), server_default='', nullable=False))
    op.add_column('panel_application', sa.Column('has_cost', sa.Boolean(), server_default='False', nullable=False))
    op.add_column('panel_application', sa.Column('length_reason', sa.Unicode(), server_default='', nullable=False))
    op.add_column('panel_application', sa.Column('length_text', sa.Unicode(), server_default='', nullable=False))
    op.add_column('panel_application', sa.Column('livestream', sa.Integer(), server_default=str(c.DONT_CARE), nullable=False))
    op.add_column('panel_application', sa.Column('need_tables', sa.Boolean(), server_default='False', nullable=False))
    op.add_column('panel_application', sa.Column('tables_desc', sa.Unicode(), server_default='', nullable=False))

    # In order to preserve data during the upgrade, we copy 'length' into 'length_text'
    connection = op.get_bind()

    for panel_app in connection.execute(panel_app_helper.select()):
        new_length_text = panel_app.length
        connection.execute(
            panel_app_helper.update().where(
                panel_app_helper.c.id == panel_app.id
            ).values(
                length_text=new_length_text,
                length=c.OTHER,
                length_reason="Automated data migration."
            )
        )

    # Converting from string to integer normally requires raw SQL
    # Let's just drop and re-add the column since we moved the data
    op.drop_column('panel_application', 'length')
    op.add_column('panel_application', sa.Column('length', sa.Integer(), server_default=str(c.SIXTY_MIN), nullable=False))



def downgrade():
    op.alter_column('panel_application', 'length', type_=sa.Unicode(), server_default='', nullable=False)
    op.drop_column('panel_application', 'tables_desc')
    op.drop_column('panel_application', 'need_tables')
    op.drop_column('panel_application', 'livestream')
    op.drop_column('panel_application', 'length_text')
    op.drop_column('panel_application', 'length_reason')
    op.drop_column('panel_application', 'has_cost')
    op.drop_column('panel_application', 'extra_info')
    op.drop_column('panel_application', 'cost_desc')
