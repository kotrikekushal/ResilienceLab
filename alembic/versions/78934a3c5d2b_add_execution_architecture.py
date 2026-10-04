"""add execution architecture

Revision ID: 78934a3c5d2b
Revises: 599062cfdb1e
Create Date: 2026-09-11 17:52:13.750698

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78934a3c5d2b'
down_revision: Union[str, Sequence[str], None] = '599062cfdb1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Create executions table first because metrics and results
    # reference it through execution_id.
    op.create_table(
        'executions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('experiment_id', sa.UUID(), nullable=False),
        sa.Column('run_number', sa.Integer(), nullable=False),
        sa.Column('run_type', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['experiment_id'],
            ['experiments.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(
        op.f('ix_executions_experiment_id'),
        'executions',
        ['experiment_id'],
        unique=False,
    )

    # Update metrics to reference executions instead of experiments.
    op.add_column(
        'metrics',
        sa.Column('execution_id', sa.UUID(), nullable=False),
    )

    op.create_index(
        op.f('ix_metrics_execution_id'),
        'metrics',
        ['execution_id'],
        unique=False,
    )

    op.drop_constraint(
        op.f('metrics_experiment_id_fkey'),
        'metrics',
        type_='foreignkey',
    )

    op.create_foreign_key(
        None,
        'metrics',
        'executions',
        ['execution_id'],
        ['id'],
        ondelete='CASCADE',
    )

    op.drop_column(
        'metrics',
        'experiment_id',
    )

    # Update results to reference executions instead of experiments.
    op.add_column(
        'results',
        sa.Column('execution_id', sa.UUID(), nullable=False),
    )

    op.drop_constraint(
        op.f('results_experiment_id_key'),
        'results',
        type_='unique',
    )

    op.create_index(
        op.f('ix_results_execution_id'),
        'results',
        ['execution_id'],
        unique=True,
    )

    op.drop_constraint(
        op.f('results_experiment_id_fkey'),
        'results',
        type_='foreignkey',
    )

    op.create_foreign_key(
        None,
        'results',
        'executions',
        ['execution_id'],
        ['id'],
        ondelete='CASCADE',
    )

    op.drop_column(
        'results',
        'experiment_id',
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Restore results.experiment_id first.
    op.add_column(
        'results',
        sa.Column(
            'experiment_id',
            sa.UUID(),
            autoincrement=False,
            nullable=False,
        ),
    )

    op.drop_constraint(
        None,
        'results',
        type_='foreignkey',
    )

    op.create_foreign_key(
        op.f('results_experiment_id_fkey'),
        'results',
        'experiments',
        ['experiment_id'],
        ['id'],
        ondelete='CASCADE',
    )

    op.drop_index(
        op.f('ix_results_execution_id'),
        table_name='results',
    )

    op.create_unique_constraint(
        op.f('results_experiment_id_key'),
        'results',
        ['experiment_id'],
        postgresql_nulls_not_distinct=False,
    )

    op.drop_column(
        'results',
        'execution_id',
    )

    # Restore metrics.experiment_id.
    op.add_column(
        'metrics',
        sa.Column(
            'experiment_id',
            sa.UUID(),
            autoincrement=False,
            nullable=False,
        ),
    )

    op.drop_constraint(
        None,
        'metrics',
        type_='foreignkey',
    )

    op.create_foreign_key(
        op.f('metrics_experiment_id_fkey'),
        'metrics',
        'experiments',
        ['experiment_id'],
        ['id'],
        ondelete='CASCADE',
    )

    op.drop_index(
        op.f('ix_metrics_execution_id'),
        table_name='metrics',
    )

    op.drop_column(
        'metrics',
        'execution_id',
    )

    # executions must be dropped last because metrics and results
    # depended on it.
    op.drop_index(
        op.f('ix_executions_experiment_id'),
        table_name='executions',
    )

    op.drop_table(
        'executions',
    )