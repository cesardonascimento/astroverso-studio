"""tabelas iniciais"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('generations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('instance', sa.String(length=64), nullable=False),
    sa.Column('algorithm', sa.String(length=64), nullable=False),
    sa.Column('inputs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('state', sa.String(length=32), nullable=False),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('source', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('original_key', sa.Text(), nullable=True),
    sa.Column('original_deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('cost_usd', sa.Numeric(precision=10, scale=5), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_generations_instance'), 'generations', ['instance'], unique=False)
    op.create_table('llm_calls',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('generation_id', sa.Integer(), nullable=True),
    sa.Column('step', sa.String(length=64), nullable=False),
    sa.Column('model', sa.String(length=64), nullable=False),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('cost_usd', sa.Numeric(precision=10, scale=5), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('ok', sa.Boolean(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['generation_id'], ['generations.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_llm_calls_generation_id'), 'llm_calls', ['generation_id'], unique=False)
    op.create_table('outputs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('generation_id', sa.Integer(), nullable=False),
    sa.Column('network', sa.String(length=64), nullable=False),
    sa.Column('strategy', sa.String(length=64), nullable=False),
    sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('state', sa.String(length=32), nullable=False),
    sa.Column('current_version', sa.Integer(), nullable=False),
    sa.Column('pending_request', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['generation_id'], ['generations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_outputs_generation_id'), 'outputs', ['generation_id'], unique=False)
    op.create_table('events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('generation_id', sa.Integer(), nullable=False),
    sa.Column('output_id', sa.Integer(), nullable=True),
    sa.Column('step', sa.String(length=64), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('ok', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['generation_id'], ['generations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['output_id'], ['outputs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_events_generation_id'), 'events', ['generation_id'], unique=False)
    op.create_table('jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('instance', sa.String(length=64), nullable=False),
    sa.Column('generation_id', sa.Integer(), nullable=False),
    sa.Column('output_id', sa.Integer(), nullable=True),
    sa.Column('step', sa.String(length=64), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('run_after', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['generation_id'], ['generations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['output_id'], ['outputs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_generation_id'), 'jobs', ['generation_id'], unique=False)
    op.create_index('jobs_claim_idx', 'jobs', ['instance', 'state', 'run_after'], unique=False)
    op.create_table('output_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('output_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('request', sa.Text(), nullable=True),
    sa.Column('plan', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('strategy_name', sa.String(length=64), nullable=False),
    sa.Column('strategy_text', sa.Text(), nullable=False),
    sa.Column('video_key', sa.Text(), nullable=True),
    sa.Column('duration_s', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('render_report', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['output_id'], ['outputs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('output_id', 'version')
    )
    op.create_index(op.f('ix_output_versions_output_id'), 'output_versions', ['output_id'], unique=False)
    op.create_table('exports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('output_version_id', sa.Integer(), nullable=False),
    sa.Column('target', sa.String(length=32), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('remote_path', sa.Text(), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['output_version_id'], ['output_versions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exports_output_version_id'), 'exports', ['output_version_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_exports_output_version_id'), table_name='exports')
    op.drop_table('exports')
    op.drop_index(op.f('ix_output_versions_output_id'), table_name='output_versions')
    op.drop_table('output_versions')
    op.drop_index('jobs_claim_idx', table_name='jobs')
    op.drop_index(op.f('ix_jobs_generation_id'), table_name='jobs')
    op.drop_table('jobs')
    op.drop_index(op.f('ix_events_generation_id'), table_name='events')
    op.drop_table('events')
    op.drop_index(op.f('ix_outputs_generation_id'), table_name='outputs')
    op.drop_table('outputs')
    op.drop_index(op.f('ix_llm_calls_generation_id'), table_name='llm_calls')
    op.drop_table('llm_calls')
    op.drop_index(op.f('ix_generations_instance'), table_name='generations')
    op.drop_table('generations')
