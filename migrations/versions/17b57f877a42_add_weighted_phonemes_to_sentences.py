"""add weighted_phonemes to sentences

Revision ID: 17b57f877a42
Revises: 47b31deb3df1
Create Date: 2025-12-20 10:59:06.327452

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '17b57f877a42'
down_revision = '47b31deb3df1'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE sentences
        ADD COLUMN IF NOT EXISTS weighted_phonemes JSON;
    """)



def downgrade():
    op.execute("""
        ALTER TABLE sentences
        DROP COLUMN IF EXISTS weighted_phonemes;
    """)
