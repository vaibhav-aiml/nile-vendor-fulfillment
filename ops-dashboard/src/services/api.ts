import {
  FulfillmentRequest,
  VendorContact,
  OpsStatusUpdatePayload,
  FulfillmentStatus,
} from "../types";

const DEFAULT_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8005";
const DEFAULT_TOKEN = process.env.NEXT_PUBLIC_OPS_TOKEN || "";

export function getOpsToken(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("nile_ops_token") || DEFAULT_TOKEN;
  }
  return DEFAULT_TOKEN;
}

export function setOpsToken(token: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("nile_ops_token", token);
  }
}

export function getBaseUrl(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("nile_api_url") || DEFAULT_BASE_URL;
  }
  return DEFAULT_BASE_URL;
}

export async function checkHealth(): Promise<{ status: string; environment?: string }> {
  try {
    const res = await fetch(`${getBaseUrl()}/health`);
    if (!res.ok) throw new Error("Health check failed");
    return await res.json();
  } catch (err) {
    return { status: "offline" };
  }
}

export async function fetchOpsRequests(params?: {
  status?: string;
  sla_breached?: boolean;
  search?: string;
}): Promise<{ items: FulfillmentRequest[]; total: number }> {
  const url = new URL(`${getBaseUrl()}/api/v1/ops/requests`);
  if (params?.status && params.status !== "ALL") {
    url.searchParams.set("status", params.status);
  }
  if (params?.sla_breached) {
    url.searchParams.set("sla_breached", "true");
  }

  const res = await fetch(url.toString(), {
    headers: {
      "Content-Type": "application/json",
      "X-Ops-Token": getOpsToken(),
    },
  });

  if (res.status === 401) {
    throw new Error("Unauthorized: Invalid Ops Token. Please check X-Ops-Token header.");
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch requests: ${res.statusText}`);
  }

  const data = await res.json();
  let items = data.items as FulfillmentRequest[];

  // Client-side search by itinerary_id or vendor name if requested
  if (params?.search && params.search.trim() !== "") {
    const term = params.search.toLowerCase();
    items = items.filter(
      (r) =>
        r.itinerary_id.toLowerCase().includes(term) ||
        r.notes?.toLowerCase().includes(term) ||
        r.vendor?.name.toLowerCase().includes(term)
    );
  }

  return { items, total: data.total };
}

export async function fetchVendorContact(vendorId: string): Promise<VendorContact> {
  const res = await fetch(`${getBaseUrl()}/api/v1/ops/vendors/${vendorId}/contact`, {
    headers: {
      "Content-Type": "application/json",
      "X-Ops-Token": getOpsToken(),
    },
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch vendor contact: ${res.statusText}`);
  }
  return await res.json();
}

export async function updateRequestStatus(
  requestId: string,
  payload: OpsStatusUpdatePayload
): Promise<FulfillmentRequest> {
  const res = await fetch(`${getBaseUrl()}/api/v1/ops/requests/${requestId}/status`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-Ops-Token": getOpsToken(),
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(`Status update failed: ${errBody}`);
  }
  return await res.json();
}
