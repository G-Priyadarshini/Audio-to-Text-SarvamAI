"""Add Sarvam job-based API columns to transcription_jobs

Revision ID: 20260303_sarvam
Revises: 60c6d0ead626
Create Date: 2026-03-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260303_sarvam'
down_revision: Union[str, None] = '60c6d0ead626'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new Sarvam job-based API columns
    op.add_column('transcription_jobs', sa.Column('sarvam_job_id', sa.String(255), nullable=True))
    op.add_column('transcription_jobs', sa.Column('sarvam_upload_url', sa.Text(), nullable=True))
    op.add_column('transcription_jobs', sa.Column('sarvam_state', sa.String(20), nullable=True))
    op.add_column('transcription_jobs', sa.Column('sarvam_poll_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('transcription_jobs', sa.Column('sarvam_last_polled_at', sa.DateTime(), nullable=True))
    op.create_index('ix_transcription_jobs_sarvam_job_id', 'transcription_jobs', ['sarvam_job_id'])

    # Extend the JobStatus enum with new values.
    # For MySQL, ALTER the enum column to include the new values.
    # For SQLite (dev mode), enum is stored as VARCHAR so no ALTER needed.
    bind = op.get_bind()
    if bind.dialect.name == 'mysql':
        op.execute(
            "ALTER TABLE transcription_jobs MODIFY COLUMN status "
            "ENUM('QUEUED','PROCESSING','STREAMING','UPLOADING_TO_SARVAM',"
            "'SARVAM_PROCESSING','DOWNLOADING_RESULT','COMPLETED','FAILED') "
            "NOT NULL"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'mysql':
        op.execute(
            "ALTER TABLE transcription_jobs MODIFY COLUMN status "
            "ENUM('QUEUED','PROCESSING','STREAMING','COMPLETED','FAILED') "
            "NOT NULL"
        )

    op.drop_index('ix_transcription_jobs_sarvam_job_id', table_name='transcription_jobs')
    op.drop_column('transcription_jobs', 'sarvam_last_polled_at')
    op.drop_column('transcription_jobs', 'sarvam_poll_count')
    op.drop_column('transcription_jobs', 'sarvam_state')
    op.drop_column('transcription_jobs', 'sarvam_upload_url')
    op.drop_column('transcription_jobs', 'sarvam_job_id')
