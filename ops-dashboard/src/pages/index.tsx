import React, { useState, useEffect } from "react";
import Head from "next/head";
import {
  fetchOpsRequests,
  fetchVendorContact,
  updateRequestStatus,
  checkHealth,
  getOpsToken,
  setOpsToken,
} from "../services/api";
import {
  FulfillmentRequest,
  VendorContact,
  FulfillmentStatus,
} from "../types";

export default function OpsDashboard() {
  const [requests, setRequests] = useState<FulfillmentRequest[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<string>("checking...");
  const [activeTab, setActiveTab] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Token configuration modal
  const [showTokenModal, setShowTokenModal] = useState<boolean>(false);
  const [tokenInput, setTokenInput] = useState<string>("");

  // Outreach & Status Modal
  const [selectedRequest, setSelectedRequest] = useState<FulfillmentRequest | null>(null);
  const [vendorContact, setVendorContact] = useState<VendorContact | null>(null);
  const [loadingContact, setLoadingContact] = useState<boolean>(false);
  const [updating, setUpdating] = useState<boolean>(false);

  // Form fields
  const [formStatus, setFormStatus] = useState<FulfillmentStatus>("OUTREACH_IN_PROGRESS");
  const [formPrice, setFormPrice] = useState<string>("");
  const [formAgent, setFormAgent] = useState<string>("ops_staff_1");
  const [formNotes, setFormNotes] = useState<string>("");
  const [formRefId, setFormRefId] = useState<string>("");

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const h = await checkHealth();
      setHealth(h.status);

      const res = await fetchOpsRequests({
        status: activeTab === "SLA_ALERT" ? undefined : activeTab,
        sla_breached: activeTab === "SLA_ALERT" ? true : undefined,
        search: searchQuery,
      });
      setRequests(res.items);
    } catch (err: any) {
      setError(err.message || "Failed to load requests");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setTokenInput(getOpsToken());
    loadData();
    const interval = setInterval(loadData, 15000); // 15s polling
    return () => clearInterval(interval);
  }, [activeTab]);

  const handleOpenOutreach = async (req: FulfillmentRequest) => {
    setSelectedRequest(req);
    setFormStatus(req.status === "PENDING" ? "OUTREACH_IN_PROGRESS" : req.status);
    setFormPrice(req.pricing_locked ? String(req.pricing_locked) : "");
    setFormAgent(req.assigned_ops_agent || "ops_staff_1");
    setFormNotes("");
    setFormRefId(req.external_reference_id || "");

    setLoadingContact(true);
    try {
      const contact = await fetchVendorContact(req.vendor_id);
      setVendorContact(contact);
    } catch (err) {
      console.error("Could not fetch contact details", err);
    } finally {
      setLoadingContact(false);
    }
  };

  const handleSaveStatus = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRequest) return;

    setUpdating(true);
    try {
      await updateRequestStatus(selectedRequest.id, {
        status: formStatus,
        pricing_locked: formPrice ? parseFloat(formPrice) : undefined,
        assigned_ops_agent: formAgent,
        notes: formNotes,
        external_reference_id: formRefId,
      });
      setSelectedRequest(null);
      await loadData();
    } catch (err: any) {
      alert(`Update failed: ${err.message}`);
    } finally {
      setUpdating(false);
    }
  };

  // KPIs
  const totalCount = requests.length;
  const pendingCount = requests.filter((r) => r.status === "PENDING").length;
  const inProgressCount = requests.filter((r) => r.status === "OUTREACH_IN_PROGRESS").length;
  const confirmedCount = requests.filter((r) => r.status === "CONFIRMED").length;
  const slaAlertCount = requests.filter((r) => r.is_sla_breached).length;

  return (
    <>
      <Head>
        <title>NILE Ops Portal — Vendor Fulfillment</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <main className="container">
        {/* Header */}
        <header className="header">
          <div>
            <div className="logo-badge">NILE • Travel Planning Pipeline (Stage 5)</div>
            <h1 className="title">Vendor Partnership & Fulfillment</h1>
            <p className="subtitle">
              Human-in-the-Loop (HITL) Manual Outreach & SLA Operations Console
            </p>
          </div>

          <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                fontSize: "0.8rem",
                color: health === "healthy" ? "#34d399" : "#f87171",
                background: "rgba(255,255,255,0.05)",
                padding: "0.35rem 0.75rem",
                borderRadius: "9999px",
                border: "1px solid var(--border-color)",
              }}
            >
              <span
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  background: health === "healthy" ? "#10b981" : "#ef4444",
                }}
              />
              Backend: {health}
            </span>

            <button
              className="btn-secondary"
              onClick={() => setShowTokenModal(true)}
              title="Configure Ops Secret Token"
            >
              🔑 Token
            </button>

            <button className="btn-secondary" onClick={loadData}>
              ↻ Refresh
            </button>
          </div>
        </header>

        {/* Metrics Grid */}
        <section className="metrics-grid">
          <div className="metric-card">
            <span className="metric-label">All Active</span>
            <span className="metric-value">{totalCount}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Pending</span>
            <span className="metric-value" style={{ color: "#fbbf24" }}>
              {pendingCount}
            </span>
          </div>
          <div className="metric-card">
            <span className="metric-label">In Outreach</span>
            <span className="metric-value" style={{ color: "#818cf8" }}>
              {inProgressCount}
            </span>
          </div>
          <div className="metric-card">
            <span className="metric-label">SLA Breached</span>
            <span className="metric-value" style={{ color: "#f87171" }}>
              {slaAlertCount}
            </span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Confirmed</span>
            <span className="metric-value" style={{ color: "#34d399" }}>
              {confirmedCount}
            </span>
          </div>
        </section>

        {/* Filters & Search */}
        <section className="filter-bar">
          <div className="status-tabs">
            {[
              { label: "All", val: "ALL" },
              { label: "Pending", val: "PENDING" },
              { label: "In Outreach", val: "OUTREACH_IN_PROGRESS" },
              { label: "🚨 SLA Alert", val: "SLA_ALERT" },
              { label: "Confirmed", val: "CONFIRMED" },
              { label: "Alternate Needed", val: "ALTERNATE_NEEDED" },
            ].map((tab) => (
              <button
                key={tab.val}
                className={`tab-btn ${activeTab === tab.val ? "active" : ""}`}
                onClick={() => setActiveTab(tab.val)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div style={{ minWidth: "240px" }}>
            <input
              type="text"
              className="search-input"
              placeholder="Search itinerary, vendor, notes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadData()}
            />
          </div>
        </section>

        {/* Content list */}
        {error && (
          <div
            style={{
              padding: "1rem",
              background: "rgba(239,68,68,0.15)",
              border: "1px solid #ef4444",
              borderRadius: "8px",
              marginBottom: "1.5rem",
              color: "#fca5a5",
            }}
          >
            ⚠️ {error}
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
            Loading fulfillment requests...
          </div>
        ) : requests.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              padding: "3.5rem",
              background: "var(--bg-card)",
              borderRadius: "10px",
              border: "1px solid var(--border-color)",
              color: "var(--text-secondary)",
            }}
          >
            No fulfillment requests matching current filters.
          </div>
        ) : (
          <div className="requests-container">
            {requests.map((req) => {
              const isBreached = req.is_sla_breached;
              const statusClass =
                req.status === "CONFIRMED"
                  ? "badge-confirmed"
                  : req.status === "OUTREACH_IN_PROGRESS"
                  ? "badge-progress"
                  : req.status === "PENDING"
                  ? "badge-pending"
                  : "badge-alert";

              return (
                <div
                  key={req.id}
                  className={`request-card ${isBreached ? "sla-breached" : ""}`}
                >
                  <div className="card-top">
                    <div>
                      <div className="vendor-title">
                        {req.vendor?.name || `Vendor ${req.vendor_id.slice(0, 8)}...`}
                      </div>
                      <div className="itinerary-tag">
                        Itinerary: <strong>{req.itinerary_id}</strong> • Req: {req.id.slice(0, 8)}
                      </div>
                    </div>

                    <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
                      <span className={`badge ${statusClass}`}>{req.status.replace(/_/g, " ")}</span>
                      <span className="badge badge-channel">
                        {req.booking_channel === "PROGRAMMATIC_API" ? "⚡ API" : "📞 HITL"}
                      </span>
                    </div>
                  </div>

                  <div className="card-details">
                    <div className="card-detail-item">
                      <span>Group Size</span>
                      <strong>{req.group_size} travelers</strong>
                    </div>

                    <div className="card-detail-item">
                      <span>Locked Price</span>
                      <strong>
                        {req.pricing_locked ? `₹${req.pricing_locked}` : "Pending confirmation"}
                      </strong>
                    </div>

                    <div className="card-detail-item">
                      <span>SLA Deadline</span>
                      <strong style={{ color: isBreached ? "#f87171" : "inherit" }}>
                        {req.sla_deadline
                          ? new Date(req.sla_deadline).toLocaleString([], {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "N/A"}
                        {isBreached && " (BREACHED)"}
                      </strong>
                    </div>

                    <div className="card-detail-item">
                      <span>Assigned Agent</span>
                      <strong>{req.assigned_ops_agent || "Unassigned"}</strong>
                    </div>
                  </div>

                  {req.notes && (
                    <div
                      style={{
                        fontSize: "0.78rem",
                        color: "var(--text-secondary)",
                        background: "rgba(0,0,0,0.25)",
                        padding: "0.5rem 0.75rem",
                        borderRadius: "6px",
                        whiteSpace: "pre-line",
                      }}
                    >
                      {req.notes}
                    </div>
                  )}

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                    <button
                      className="btn-primary"
                      onClick={() => handleOpenOutreach(req)}
                    >
                      📞 Outreach & Update
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Modal for Token Setup */}
        {showTokenModal && (
          <div className="modal-overlay" onClick={() => setShowTokenModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <h2 style={{ fontSize: "1.2rem", fontWeight: 700 }}>Ops Authentication Secret</h2>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                This dashboard uses the static <code>X-Ops-Token</code> header configured in{" "}
                <code>.env</code>.
              </p>

              <div className="form-group">
                <label className="form-label">X-Ops-Token Value</label>
                <input
                  type="text"
                  className="form-control"
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button className="btn-secondary" onClick={() => setShowTokenModal(false)}>
                  Cancel
                </button>
                <button
                  className="btn-primary"
                  onClick={() => {
                    setOpsToken(tokenInput);
                    setShowTokenModal(false);
                    loadData();
                  }}
                >
                  Save Token
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal for Outreach & Status Update */}
        {selectedRequest && (
          <div className="modal-overlay" onClick={() => setSelectedRequest(null)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h2 style={{ fontSize: "1.25rem", fontWeight: 700 }}>Vendor Outreach Console</h2>
                <button
                  style={{ background: "none", border: "none", color: "#fff", cursor: "pointer", fontSize: "1.2rem" }}
                  onClick={() => setSelectedRequest(null)}
                >
                  ✕
                </button>
              </div>

              {/* Vendor Contact Information Card */}
              <div className="contact-card">
                <div style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--accent-cyan)", fontWeight: 700 }}>
                  Direct Vendor Contact Details
                </div>
                {loadingContact ? (
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Loading contact info...</div>
                ) : vendorContact ? (
                  <>
                    <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#fff" }}>
                      {vendorContact.name}
                    </div>
                    {vendorContact.contact_name && (
                      <div style={{ fontSize: "0.875rem" }}>
                        Contact Person: <strong>{vendorContact.contact_name}</strong>
                      </div>
                    )}
                    {vendorContact.contact_phone && (
                      <div>
                        <a className="contact-link" href={`tel:${vendorContact.contact_phone}`}>
                          📞 {vendorContact.contact_phone} (Click to Call)
                        </a>
                      </div>
                    )}
                    {vendorContact.contact_email && (
                      <div>
                        <a className="contact-link" href={`mailto:${vendorContact.contact_email}`}>
                          ✉️ {vendorContact.contact_email} (Send Email)
                        </a>
                      </div>
                    )}
                    {vendorContact.address && (
                      <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                        📍 {vendorContact.address}
                      </div>
                    )}
                  </>
                ) : (
                  <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                    No additional contact metadata on file for this vendor.
                  </div>
                )}
              </div>

              {/* Status Update Form */}
              <form onSubmit={handleSaveStatus} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div className="form-group">
                  <label className="form-label">Booking Outcome / Status</label>
                  <select
                    className="form-control"
                    value={formStatus}
                    onChange={(e) => setFormStatus(e.target.value as FulfillmentStatus)}
                  >
                    <option value="OUTREACH_IN_PROGRESS">Outreach In Progress (Contact initiated)</option>
                    <option value="CONFIRMED">Confirmed (Vendor accepted & slot secured)</option>
                    <option value="REJECTED">Rejected (Vendor declined or sold out)</option>
                    <option value="ALTERNATE_NEEDED">Alternate Needed (Requires alternate vendor discovery)</option>
                    <option value="CANCELLED">Cancelled (Customer/internal cancellation)</option>
                  </select>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div className="form-group">
                    <label className="form-label">Locked Price (₹)</label>
                    <input
                      type="number"
                      step="0.01"
                      className="form-control"
                      placeholder="e.g. 3500.00"
                      value={formPrice}
                      onChange={(e) => setFormPrice(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Voucher / Confirmation #</label>
                    <input
                      type="text"
                      className="form-control"
                      placeholder="e.g. CONF-9821"
                      value={formRefId}
                      onChange={(e) => setFormRefId(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Assigned Ops Agent</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="Agent username / ID"
                    value={formAgent}
                    onChange={(e) => setFormAgent(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Outreach Notes / Call Outcome</label>
                  <textarea
                    rows={3}
                    className="form-control"
                    placeholder="e.g. Spoke with front desk. Confirmed ocean-view room for 2 guests. Advance paid."
                    value={formNotes}
                    onChange={(e) => setFormNotes(e.target.value)}
                  />
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setSelectedRequest(null)}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="btn-primary" disabled={updating}>
                    {updating ? "Saving..." : "Save Status & Emit Event"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </>
  );
}
