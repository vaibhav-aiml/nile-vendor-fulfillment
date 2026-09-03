export type FulfillmentStatus =
  | "PENDING"
  | "OUTREACH_IN_PROGRESS"
  | "CONFIRMED"
  | "REJECTED"
  | "ALTERNATE_NEEDED"
  | "CANCELLED";

export type BookingChannel = "PROGRAMMATIC_API" | "HITL_MANUAL";

export type PartnershipStatus = "PARTNERED" | "NON_PARTNERED";

export type VendorCategory =
  | "STAY"
  | "ACTIVITY"
  | "TRANSPORT"
  | "DINING"
  | "GUIDE"
  | "OTHER";

export interface VendorSummary {
  id: string;
  name: string;
  category: VendorCategory;
  partnership_status: PartnershipStatus;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  address?: string;
}

export interface FulfillmentRequest {
  id: string;
  itinerary_id: string;
  vendor_id: string;
  status: FulfillmentStatus;
  booking_channel: BookingChannel;
  service_date_start?: string;
  service_date_end?: string;
  group_size: number;
  pricing_locked?: number;
  assigned_ops_agent?: string;
  sla_deadline?: string;
  notes?: string;
  external_reference_id?: string;
  created_at: string;
  updated_at: string;
  is_sla_breached?: boolean;
  vendor?: VendorSummary;
}

export interface VendorContact {
  id: string;
  name: string;
  category: VendorCategory;
  partnership_status: PartnershipStatus;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  address?: string;
}

export interface OpsStatusUpdatePayload {
  status: FulfillmentStatus;
  pricing_locked?: number;
  assigned_ops_agent?: string;
  notes?: string;
  external_reference_id?: string;
}
