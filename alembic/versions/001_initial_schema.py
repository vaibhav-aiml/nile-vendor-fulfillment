"""Initial database schema with PostGIS support

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-03 08:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # 2. Create Vendors table
    op.create_table(
        'vendors',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column(
            'category',
            sa.Enum('STAY', 'ACTIVITY', 'TRANSPORT', 'DINING', 'GUIDE', 'OTHER', name='vendor_category_enum'),
            nullable=False,
            server_default='OTHER',
        ),
        sa.Column(
            'partnership_status',
            sa.Enum('PARTNERED', 'NON_PARTNERED', name='partnership_status_enum'),
            nullable=False,
            server_default='NON_PARTNERED',
        ),
        sa.Column(
            'verification_status',
            sa.Enum('VERIFIED', 'UNVERIFIED', 'SUSPENDED', name='verification_status_enum'),
            nullable=False,
            server_default='UNVERIFIED',
        ),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column(
            'location',
            geoalchemy2.Geometry(geometry_type='POINT', srid=4326, spatial_index=True, from_text='ST_GeomFromEWKT', name='geometry'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_vendors_name', 'vendors', ['name'])
    op.create_index('ix_vendors_partnership_status', 'vendors', ['partnership_status'])

    # 3. Create Fulfillment Requests table
    op.create_table(
        'fulfillment_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('itinerary_id', sa.String(length=100), nullable=False),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False),
        sa.Column(
            'status',
            sa.Enum('PENDING', 'OUTREACH_IN_PROGRESS', 'CONFIRMED', 'REJECTED', 'ALTERNATE_NEEDED', 'CANCELLED', name='fulfillment_status_enum'),
            nullable=False,
            server_default='PENDING',
        ),
        sa.Column(
            'booking_channel',
            sa.Enum('PROGRAMMATIC_API', 'HITL_MANUAL', name='booking_channel_enum'),
            nullable=False,
            server_default='HITL_MANUAL',
        ),
        sa.Column('service_date_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('service_date_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('group_size', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('pricing_locked', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('assigned_ops_agent', sa.String(length=100), nullable=True),
        sa.Column('sla_deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('external_reference_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('itinerary_id', 'vendor_id', name='uq_itinerary_vendor'),
    )
    op.create_index('ix_fulfillment_requests_itinerary_id', 'fulfillment_requests', ['itinerary_id'])
    op.create_index('ix_fulfillment_requests_vendor_id', 'fulfillment_requests', ['vendor_id'])
    op.create_index('ix_fulfillment_requests_status', 'fulfillment_requests', ['status'])
    op.create_index('ix_fulfillment_requests_assigned_ops_agent', 'fulfillment_requests', ['assigned_ops_agent'])
    op.create_index('ix_fulfillment_requests_sla_deadline', 'fulfillment_requests', ['sla_deadline'])


def downgrade() -> None:
    op.drop_table('fulfillment_requests')
    op.drop_table('vendors')
    op.execute("DROP TYPE IF EXISTS booking_channel_enum;")
    op.execute("DROP TYPE IF EXISTS fulfillment_status_enum;")
    op.execute("DROP TYPE IF EXISTS verification_status_enum;")
    op.execute("DROP TYPE IF EXISTS partnership_status_enum;")
    op.execute("DROP TYPE IF EXISTS vendor_category_enum;")
