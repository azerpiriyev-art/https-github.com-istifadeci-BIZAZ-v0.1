"use client";

import { FormEvent, useEffect, useState, type CSSProperties } from "react";
import { useRouter } from "next/navigation";

const API_URL = "http://127.0.0.1:8001";
const TOKEN_KEY = "bizaz_token";
const NEED_STORAGE_KEY = "bizaz_current_need";
const APPROVAL_STORAGE_KEY = "bizaz_current_need_approval";

type Product = {
  id: string;
  name: string;
  sku?: string | null;
  unit: string;
  is_active: boolean;
};

type NeedItem = {
  product_id: string;
  quantity: string;
  unit: string;
  required_date: string;
  specifications: string;
  notes: string;
};

type NeedResponse = {
  id: string;
  company_id: string;
  need_number: string;
  source: string;
  status: string;
  title: string;
  description: string | null;
  requested_by: string;
  required_date: string | null;
  priority: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
  items: Array<{
    id: string;
    need_id: string;
    product_id: string;
    quantity: number | string;
    unit: string;
    required_date: string | null;
    specifications: string | null;
    notes: string | null;
    created_at: string;
    updated_at: string;
  }>;
};

type ApprovalStep = {
  id: string;
  approval_request_id: string;
  step_order: number;
  status: string;
  approver_user_id: string | null;
  approver_role: string | null;
  acted_by: string | null;
  acted_at: string | null;
  comment: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type ApprovalResponse = {
  id: string;
  company_id: string;
  entity_type: string;
  entity_id: string;
  status: string;
  execution_mode: string;
  decision_mode: string;
  priority: string;
  policy_key: string | null;
  policy_version: string | null;
  requested_by: string;
  requested_at: string;
  completed_at: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  steps: ApprovalStep[];
};

type NeedForm = {
  needNumber: string;
  source: "MANUAL" | "PROJECT" | "INVENTORY";
  title: string;
  description: string;
  requiredDate: string;
  priority: "LOW" | "NORMAL" | "HIGH" | "URGENT";
  notes: string;
  items: NeedItem[];
};

const emptyItem = (): NeedItem => ({
  product_id: "",
  quantity: "",
  unit: "",
  required_date: "",
  specifications: "",
  notes: "",
});

const initialForm = (): NeedForm => ({
  needNumber: "",
  source: "MANUAL",
  title: "",
  description: "",
  requiredDate: "",
  priority: "NORMAL",
  notes: "",
  items: [emptyItem()],
});

function formatError(data: unknown, fallback: string) {
  if (typeof data === "object" && data !== null && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((entry) => {
          if (typeof entry === "object" && entry !== null && "msg" in entry) {
            return String((entry as { msg?: unknown }).msg);
          }
          return String(entry);
        })
        .join("; ");
    }
    if (detail) return JSON.stringify(detail);
  }
  return fallback;
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    DRAFT: "Qaralama",
    SUBMITTED: "Təqdim edilib",
    UNDER_REVIEW: "Yoxlamada",
    APPROVED: "Təsdiqlənib",
    REJECTED: "Rədd edilib",
    CANCELLED: "Ləğv edilib",
    EXPIRED: "Müddəti bitib",
    PENDING: "Gözləyir",
    APPROVE: "Təsdiq",
    REJECT: "Rədd",
  };
  return labels[status] || status;
}

export default function NewNeedPage() {
  const router = useRouter();

  const [form, setForm] = useState<NeedForm>(initialForm());
  const [products, setProducts] = useState<Product[]>([]);
  const [currentNeed, setCurrentNeed] = useState<NeedResponse | null>(null);
  const [approval, setApproval] = useState<ApprovalResponse | null>(null);
  const [approverRole, setApproverRole] = useState("OWNER");
  const [decisionComment, setDecisionComment] = useState("");
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [saving, setSaving] = useState(false);
  const [approvalSaving, setApprovalSaving] = useState(false);
  const [statusSaving, setStatusSaving] = useState(false);
  const [decisionSaving, setDecisionSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      router.replace("/login");
      return;
    }

    void loadProducts();

    const savedNeed = localStorage.getItem(NEED_STORAGE_KEY);
    if (savedNeed) {
      try {
        setCurrentNeed(JSON.parse(savedNeed) as NeedResponse);
      } catch {
        localStorage.removeItem(NEED_STORAGE_KEY);
      }
    }

    const savedApproval = localStorage.getItem(APPROVAL_STORAGE_KEY);
    if (savedApproval) {
      void loadApproval(savedApproval);
    }
  }, [router]);

  async function loadProducts() {
    setLoadingProducts(true);
    setError("");

    try {
      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) {
        router.replace("/login");
        return;
      }

      const response = await fetch(`${API_URL}/api/v1/products`, {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
        cache: "no-store",
      });

      const data = await response.json();

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(formatError(data, "Məhsullar yüklənmədi."));
      }

      setProducts(
        (Array.isArray(data) ? data : data.products || []).filter(
          (product: Product) => product.is_active
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Məhsullar yüklənmədi.");
    } finally {
      setLoadingProducts(false);
    }
  }

  async function loadApproval(approvalId: string) {
    setApprovalSaving(true);

    try {
      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) {
        router.replace("/login");
        return;
      }

      const response = await fetch(
        `${API_URL}/api/v1/approvals/requests/${approvalId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/json",
          },
          cache: "no-store",
        }
      );

      const data = await response.json();

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(formatError(data, "Approval məlumatı yüklənmədi."));
      }

      setApproval(data as ApprovalResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval məlumatı yüklənmədi.");
    } finally {
      setApprovalSaving(false);
    }
  }

  function updateItem(index: number, field: keyof NeedItem, value: string) {
    setForm((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [field]: value } : item
      ),
    }));
  }

  function selectProduct(index: number, productId: string) {
    const product = products.find((entry) => entry.id === productId);

    setForm((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) =>
        itemIndex === index
          ? { ...item, product_id: productId, unit: product?.unit || item.unit }
          : item
      ),
    }));
  }

  function addItem() {
    setForm((current) => ({
      ...current,
      items: [...current.items, emptyItem()],
    }));
  }

  function removeItem(index: number) {
    setForm((current) => ({
      ...current,
      items:
        current.items.length === 1
          ? current.items
          : current.items.filter((_, itemIndex) => itemIndex !== index),
    }));
  }

  async function createNeed(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");

    if (!form.needNumber.trim()) {
      setError("Tələbat nömrəsi daxil edilməlidir.");
      return;
    }

    if (!form.title.trim()) {
      setError("Başlıq daxil edilməlidir.");
      return;
    }

    if (
      form.items.some(
        (item) =>
          !item.product_id ||
          !item.quantity ||
          Number(item.quantity) <= 0 ||
          !item.unit.trim()
      )
    ) {
      setError("Bütün məhsul sətirlərində məhsul, miqdar və ölçü vahidi doldurulmalıdır.");
      return;
    }

    try {
      setSaving(true);

      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) {
        router.replace("/login");
        return;
      }

      const payload = {
        need_number: form.needNumber.trim(),
        source: form.source,
        title: form.title.trim(),
        description: form.description.trim() || null,
        required_date: form.requiredDate || null,
        priority: form.priority,
        notes: form.notes.trim() || null,
        items: form.items.map((item) => ({
          product_id: item.product_id,
          quantity: Number(item.quantity),
          unit: item.unit.trim(),
          required_date: item.required_date || null,
          specifications: item.specifications.trim() || null,
          notes: item.notes.trim() || null,
        })),
      };

      const response = await fetch(`${API_URL}/api/v1/needs`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(formatError(data, "Tələbat yaradılmadı."));
      }

      setCurrentNeed(data as NeedResponse);
      setApproval(null);
      localStorage.setItem(NEED_STORAGE_KEY, JSON.stringify(data));
      localStorage.removeItem(APPROVAL_STORAGE_KEY);

      setMessage(`Tələbat ${data.need_number} yaradıldı.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tələbat yaradılmadı.");
    } finally {
      setSaving(false);
    }
  }

  async function updateNeedStatus(status: string) {
    if (!currentNeed) return;

    setError("");
    setMessage("");

    try {
      setStatusSaving(true);

      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) {
        router.replace("/login");
        return;
      }

      const response = await fetch(
        `${API_URL}/api/v1/needs/${currentNeed.id}/status`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({ status }),
        }
      );

      const data = await response.json();

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(formatError(data, `Status ${statusLabel(status)} edilmədi.`));
      }

      const updated: NeedResponse = {
        ...currentNeed,
        status: data.new_status || data.status || status,
        updated_at: data.updated_at || new Date().toISOString(),
      };

      setCurrentNeed(updated);
      localStorage.setItem(NEED_STORAGE_KEY, JSON.stringify(updated));
      setMessage(`Tələbat statusı ${statusLabel(updated.status)} oldu.`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : `Tələbat statusı dəyişdirilmədi.`
      );
    } finally {
      setStatusSaving(false);
    }
  }

  async function createApproval() {
    if (!currentNeed) return;

    setError("");
    setMessage("");

    if (!["SUBMITTED", "UNDER_REVIEW"].includes(currentNeed.status)) {
      setError("Approval yaratmaq üçün tələbat təqdim edilmiş və ya yoxlamada olmalıdır.");
      return;
    }

    if (!approverRole.trim()) {
      setError("Təsdiq edən rol daxil edilməlidir.");
      return;
    }

    try {
      setApprovalSaving(true);

      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) {
        router.replace("/login");
        return;
      }

      const payload = {
        entity_type: "NEED",
        entity_id: currentNeed.id,
        execution_mode: "SEQUENTIAL",
        decision_mode: "ALL",
        priority: currentNeed.priority,
        policy_key: null,
        policy_version: null,
        steps: [
          {
            step_order: 1,
            approver_user_id: null,
            approver_role: approverRole.trim(),
          },
        ],
      };

      const response = await fetch(`${API_URL}/api/v1/approvals/requests`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(formatError(data, "Approval request yaradılmadı."));
      }

      setApproval(data as ApprovalResponse);
      localStorage.setItem(APPROVAL_STORAGE_KEY, data.id);
      setMessage("Approval request yaradıldı.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval request yaradılmadı.");
    } finally {
      setApprovalSaving(false);
    }
  }

  async function decideApproval(decision: "APPROVE" | "REJECT") {
    if (!approval) return;

    setError("");
    setMessage("");

    try {
      setDecisionSaving(true);

      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) {
        router.replace("/login");
        return;
      }

      const response = await fetch(
        `${API_URL}/api/v1/approvals/${approval.id}/decision`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            decision,
            comment: decisionComment.trim() || null,
          }),
        }
      );

      const data = await response.json();

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(formatError(data, "Approval qərarı tətbiq edilmədi."));
      }

      await loadApproval(approval.id);
      setDecisionComment("");
      setMessage(
        decision === "APPROVE"
          ? "Approval təsdiqləndi."
          : "Approval rədd edildi."
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Approval qərarı tətbiq edilmədi."
      );
    } finally {
      setDecisionSaving(false);
    }
  }

  function resetForm() {
    setForm(initialForm());
    setCurrentNeed(null);
    setApproval(null);
    setMessage("");
    setError("");
    localStorage.removeItem(NEED_STORAGE_KEY);
    localStorage.removeItem(APPROVAL_STORAGE_KEY);
  }

  const canSubmit = currentNeed?.status === "DRAFT";
  const canReview = currentNeed?.status === "SUBMITTED";
  const canApproveNeed =
    currentNeed?.status === "UNDER_REVIEW" && approval?.status === "APPROVED";
  const canRejectNeed = currentNeed?.status === "UNDER_REVIEW";
  const canCancelNeed =
    currentNeed?.status === "DRAFT" || currentNeed?.status === "SUBMITTED";
  const approvalPending = approval?.status === "PENDING";

  return (
    <main style={styles.page}>
      <header style={styles.header}>
        <div>
          <strong style={styles.logo}>BIZAZ</strong>
          <span style={styles.headerLabel}>Tələbat və təsdiq</span>
        </div>

        <div style={styles.headerActions}>
          <button type="button" onClick={() => router.push("/dashboard")} style={styles.secondaryButton}>
            İdarəetmə paneli
          </button>
          <button
            type="button"
            onClick={() => {
              localStorage.removeItem(TOKEN_KEY);
              router.replace("/login");
            }}
            style={styles.logoutButton}
          >
            Çıxış
          </button>
        </div>
      </header>

      <section style={styles.container}>
        <div style={styles.hero}>
          <div>
            <div style={styles.eyebrow}>BIZAZ • NEED ENGINE</div>
            <h1 style={styles.title}>Yeni tələbat</h1>
            <p style={styles.subtitle}>
              Tələbat yaradın, təqdim edin, yoxlamaya keçirin və approval prosesini idarə edin.
            </p>
          </div>
          <button type="button" onClick={resetForm} style={styles.secondaryButton}>
            Yeni forma
          </button>
        </div>

        {message && <div style={styles.success}>{message}</div>}
        {error && <div style={styles.error}>{error}</div>}

        <form onSubmit={createNeed}>
          <section style={styles.card}>
            <div style={styles.sectionHeader}>
              <div>
                <h2 style={styles.sectionTitle}>Tələbat məlumatları</h2>
                <div style={styles.hint}>Backend kontraktındakı məcburi sahələr işarəsiz saxlanılıb; məcburi olanlar API tərəfindən də yoxlanılır.</div>
              </div>
              {currentNeed && (
                <div style={styles.statusBadge}>
                  {statusLabel(currentNeed.status)}
                </div>
              )}
            </div>

            <div style={styles.grid}>
              <label style={styles.field}>
                <span>Tələbat № *</span>
                <input
                  value={form.needNumber}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, needNumber: event.target.value }))
                  }
                  style={styles.input}
                  placeholder="Məsələn: NEED-2026-001"
                  disabled={Boolean(currentNeed)}
                />
              </label>

              <label style={styles.field}>
                <span>Mənbə</span>
                <select
                  value={form.source}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      source: event.target.value as NeedForm["source"],
                    }))
                  }
                  style={styles.input}
                  disabled={Boolean(currentNeed)}
                >
                  <option value="MANUAL">Manual</option>
                  <option value="PROJECT">Layihə</option>
                  <option value="INVENTORY">Anbar</option>
                </select>
              </label>

              <label style={styles.fieldWide}>
                <span>Başlıq *</span>
                <input
                  value={form.title}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, title: event.target.value }))
                  }
                  style={styles.input}
                  placeholder="Tələbatın qısa adı"
                  disabled={Boolean(currentNeed)}
                />
              </label>

              <label style={styles.field}>
                <span>Tələb olunan tarix</span>
                <input
                  type="date"
                  value={form.requiredDate}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, requiredDate: event.target.value }))
                  }
                  style={styles.input}
                  disabled={Boolean(currentNeed)}
                />
              </label>

              <label style={styles.field}>
                <span>Prioritet</span>
                <select
                  value={form.priority}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      priority: event.target.value as NeedForm["priority"],
                    }))
                  }
                  style={styles.input}
                  disabled={Boolean(currentNeed)}
                >
                  <option value="LOW">Aşağı</option>
                  <option value="NORMAL">Normal</option>
                  <option value="HIGH">Yüksək</option>
                  <option value="URGENT">Təcili</option>
                </select>
              </label>

              <label style={styles.fieldWide}>
                <span>Təsvir</span>
                <textarea
                  value={form.description}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, description: event.target.value }))
                  }
                  style={styles.textarea}
                  rows={4}
                  disabled={Boolean(currentNeed)}
                />
              </label>

              <label style={styles.fieldWide}>
                <span>Qeyd</span>
                <textarea
                  value={form.notes}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, notes: event.target.value }))
                  }
                  style={styles.textarea}
                  rows={3}
                  disabled={Boolean(currentNeed)}
                />
              </label>
            </div>
          </section>

          <section style={styles.card}>
            <div style={styles.sectionHeader}>
              <div>
                <h2 style={styles.sectionTitle}>Tələbat sətirləri</h2>
                <div style={styles.hint}>
                  Hər sətirdə məhsul, miqdar və ölçü vahidi məcburidir.
                </div>
              </div>
              <button
                type="button"
                onClick={addItem}
                style={styles.secondaryButton}
                disabled={Boolean(currentNeed)}
              >
                + Məhsul sətri
              </button>
            </div>

            {form.items.map((item, index) => (
              <div key={index} style={styles.itemCard}>
                <div style={styles.itemHeader}>
                  <strong>Sətir {index + 1}</strong>
                  {form.items.length > 1 && !currentNeed && (
                    <button
                      type="button"
                      onClick={() => removeItem(index)}
                      style={styles.dangerLink}
                    >
                      Sil
                    </button>
                  )}
                </div>

                <div style={styles.grid}>
                  <label style={styles.fieldWide}>
                    <span>Məhsul *</span>
                    <select
                      value={item.product_id}
                      onChange={(event) => selectProduct(index, event.target.value)}
                      style={styles.input}
                      disabled={Boolean(currentNeed) || loadingProducts}
                    >
                      <option value="">
                        {loadingProducts ? "Məhsullar yüklənir..." : "Məhsul seçin"}
                      </option>
                      {products.map((product) => (
                        <option key={product.id} value={product.id}>
                          {product.name}{product.sku ? ` — ${product.sku}` : ""}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label style={styles.field}>
                    <span>Miqdar *</span>
                    <input
                      type="number"
                      min="0.000001"
                      step="any"
                      value={item.quantity}
                      onChange={(event) => updateItem(index, "quantity", event.target.value)}
                      style={styles.input}
                      disabled={Boolean(currentNeed)}
                    />
                  </label>

                  <label style={styles.field}>
                    <span>Ölçü vahidi *</span>
                    <input
                      value={item.unit}
                      onChange={(event) => updateItem(index, "unit", event.target.value)}
                      style={styles.input}
                      placeholder="ədəd, kq, m, m²..."
                      disabled={Boolean(currentNeed)}
                    />
                  </label>

                  <label style={styles.field}>
                    <span>Tələb olunan tarix</span>
                    <input
                      type="date"
                      value={item.required_date}
                      onChange={(event) => updateItem(index, "required_date", event.target.value)}
                      style={styles.input}
                      disabled={Boolean(currentNeed)}
                    />
                  </label>

                  <label style={styles.fieldWide}>
                    <span>Spesifikasiya</span>
                    <textarea
                      value={item.specifications}
                      onChange={(event) => updateItem(index, "specifications", event.target.value)}
                      style={styles.textarea}
                      rows={3}
                      disabled={Boolean(currentNeed)}
                    />
                  </label>

                  <label style={styles.fieldWide}>
                    <span>Sətir qeydi</span>
                    <textarea
                      value={item.notes}
                      onChange={(event) => updateItem(index, "notes", event.target.value)}
                      style={styles.textarea}
                      rows={2}
                      disabled={Boolean(currentNeed)}
                    />
                  </label>
                </div>
              </div>
            ))}

            {!currentNeed && (
              <button type="submit" disabled={saving} style={styles.primaryButton}>
                {saving ? "Yaradılır..." : "Tələbat yarat"}
              </button>
            )}
          </section>
        </form>

        {currentNeed && (
          <>
            <section style={styles.card}>
              <div style={styles.sectionHeader}>
                <div>
                  <h2 style={styles.sectionTitle}>Tələbat workflow</h2>
                  <div style={styles.hint}>
                    Tələbat #{currentNeed.need_number} — {currentNeed.title}
                  </div>
                </div>
                <div style={styles.statusBadge}>{statusLabel(currentNeed.status)}</div>
              </div>

              <div style={styles.workflow}>
                <div style={currentNeed.status === "DRAFT" ? styles.workflowActive : styles.workflowStep}>1. Qaralama</div>
                <div style={styles.arrow}>→</div>
                <div style={currentNeed.status === "SUBMITTED" ? styles.workflowActive : styles.workflowStep}>2. Təqdim</div>
                <div style={styles.arrow}>→</div>
                <div style={currentNeed.status === "UNDER_REVIEW" ? styles.workflowActive : styles.workflowStep}>3. Yoxlama</div>
                <div style={styles.arrow}>→</div>
                <div style={currentNeed.status === "APPROVED" ? styles.workflowActive : styles.workflowStep}>4. Təsdiq</div>
              </div>

              <div style={styles.buttonRow}>
                {canSubmit && (
                  <button
                    type="button"
                    onClick={() => void updateNeedStatus("SUBMITTED")}
                    disabled={statusSaving}
                    style={styles.primaryButton}
                  >
                    Təqdim et
                  </button>
                )}

                {canReview && (
                  <button
                    type="button"
                    onClick={() => void updateNeedStatus("UNDER_REVIEW")}
                    disabled={statusSaving}
                    style={styles.primaryButton}
                  >
                    Yoxlamaya keçir
                  </button>
                )}

                {canApproveNeed && (
                  <button
                    type="button"
                    onClick={() => void updateNeedStatus("APPROVED")}
                    disabled={statusSaving}
                    style={styles.successButton}
                  >
                    Tələbatı təsdiqlə
                  </button>
                )}

                {canRejectNeed && (
                  <button
                    type="button"
                    onClick={() => void updateNeedStatus("REJECTED")}
                    disabled={statusSaving}
                    style={styles.dangerButton}
                  >
                    Tələbatı rədd et
                  </button>
                )}

                {canCancelNeed && (
                  <button
                    type="button"
                    onClick={() => void updateNeedStatus("CANCELLED")}
                    disabled={statusSaving}
                    style={styles.secondaryButton}
                  >
                    Ləğv et
                  </button>
                )}
              </div>
            </section>

            <section style={styles.card}>
              <div style={styles.sectionHeader}>
                <div>
                  <h2 style={styles.sectionTitle}>Approval</h2>
                  <div style={styles.hint}>
                    Approval qərarı ayrıca verilir; qərarın ardından Need statusı ayrıca dəyişdirilir.
                  </div>
                </div>
                {approval && (
                  <div style={styles.statusBadge}>{statusLabel(approval.status)}</div>
                )}
              </div>

              {!approval ? (
                <div>
                  <div style={styles.grid}>
                    <label style={styles.field}>
                      <span>Təsdiq edən rol *</span>
                      <input
                        value={approverRole}
                        onChange={(event) => setApproverRole(event.target.value)}
                        style={styles.input}
                        maxLength={50}
                      />
                    </label>
                  </div>

                  <button
                    type="button"
                    onClick={() => void createApproval()}
                    disabled={
                      approvalSaving ||
                      !["SUBMITTED", "UNDER_REVIEW"].includes(currentNeed.status)
                    }
                    style={styles.primaryButton}
                  >
                    {approvalSaving ? "Yaradılır..." : "Təsdiq sorğusu yarat"}
                  </button>
                </div>
              ) : (
                <>
                  <div style={styles.approvalSummary}>
                    <div>
                      <strong>Approval ID</strong>
                      <div style={styles.mono}>{approval.id}</div>
                    </div>
                    <div>
                      <strong>Entity</strong>
                      <div>{approval.entity_type}</div>
                    </div>
                    <div>
                      <strong>Prioritet</strong>
                      <div>{statusLabel(approval.priority)}</div>
                    </div>
                    <div>
                      <strong>Qərar rejimi</strong>
                      <div>{approval.decision_mode}</div>
                    </div>
                  </div>

                  <div style={{ marginTop: 20 }}>
                    <h3 style={styles.subTitle}>Approval addımları</h3>
                    {approval.steps.map((step) => (
                      <div key={step.id} style={styles.stepCard}>
                        <div>
                          <strong>#{step.step_order}</strong> — {statusLabel(step.status)}
                        </div>
                        <div style={styles.muted}>
                          Rol: {step.approver_role || "—"}
                          {step.approver_user_id ? ` | User: ${step.approver_user_id}` : ""}
                        </div>
                        {step.comment && (
                          <div style={styles.commentBox}>Şərh: {step.comment}</div>
                        )}
                      </div>
                    ))}
                  </div>

                  <div style={{ marginTop: 20 }}>
                    <label style={styles.fieldWide}>
                      <span>Qərar şərhi</span>
                      <textarea
                        value={decisionComment}
                        onChange={(event) => setDecisionComment(event.target.value)}
                        style={styles.textarea}
                        rows={3}
                        maxLength={5000}
                        placeholder="Approval qərarı üçün şərh"
                      />
                    </label>

                    <div style={styles.buttonRow}>
                      {approvalPending && (<>
                      <button
                        type="button"
                        onClick={() => void decideApproval("APPROVE")}
                        disabled={decisionSaving || !approvalPending}
                        style={styles.successButton}
                      >
                        {decisionSaving ? "Göndərilir..." : "Təsdiqlə"}
                      </button>

                      <button
                        type="button"
                        onClick={() => void decideApproval("REJECT")}
                        disabled={decisionSaving || !approvalPending}
                        style={styles.dangerButton}
                      >
                        {decisionSaving ? "Göndərilir..." : "İmtina et"}
                      </button>
                      </>) }

                      <button
                        type="button"
                        onClick={() => void loadApproval(approval.id)}
                        disabled={approvalSaving}
                        style={styles.secondaryButton}
                      >
                        {approvalSaving ? "Yüklənir..." : "Təsdiq sorğusunu yenilə"}
                      </button>
                    </div>
                  </div>
                </>
              )}
            </section>
          </>
        )}
      </section>
    </main>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: "#f5f7fa",
    fontFamily: "Arial, sans-serif",
    color: "#101828",
  },
  header: {
    background: "#ffffff",
    borderBottom: "1px solid #ddd",
    padding: "16px 30px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 16,
  },
  logo: {
    fontSize: 22,
  },
  headerLabel: {
    marginLeft: 15,
    color: "#777",
  },
  headerActions: {
    display: "flex",
    gap: 10,
  },
  container: {
    maxWidth: 1100,
    margin: "0 auto",
    padding: "40px 20px 60px",
  },
  hero: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 20,
    marginBottom: 20,
  },
  eyebrow: {
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: "0.16em",
    color: "#667085",
    marginBottom: 7,
  },
  title: {
    margin: 0,
    fontSize: 34,
  },
  subtitle: {
    marginTop: 10,
    color: "#667085",
    maxWidth: 760,
  },
  card: {
    background: "#ffffff",
    border: "1px solid #ddd",
    borderRadius: 10,
    padding: 24,
    marginBottom: 20,
  },
  sectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 15,
    marginBottom: 20,
  },
  sectionTitle: {
    margin: 0,
    fontSize: 21,
  },
  subTitle: {
    margin: "0 0 12px",
    fontSize: 17,
  },
  hint: {
    marginTop: 6,
    color: "#667085",
    fontSize: 13,
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    gap: 18,
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: 7,
    fontWeight: 600,
    fontSize: 14,
  },
  fieldWide: {
    display: "flex",
    flexDirection: "column",
    gap: 7,
    fontWeight: 600,
    fontSize: 14,
    gridColumn: "1 / -1",
  },
  input: {
    width: "100%",
    boxSizing: "border-box",
    padding: "10px 11px",
    border: "1px solid #cfd4dc",
    borderRadius: 6,
    background: "#ffffff",
    fontSize: 14,
  },
  textarea: {
    width: "100%",
    boxSizing: "border-box",
    padding: "10px 11px",
    border: "1px solid #cfd4dc",
    borderRadius: 6,
    resize: "vertical",
    fontFamily: "Arial, sans-serif",
    fontSize: 14,
  },
  itemCard: {
    border: "1px solid #e4e7ec",
    borderRadius: 8,
    padding: 18,
    marginBottom: 16,
  },
  itemHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  primaryButton: {
    marginTop: 18,
    padding: "10px 18px",
    border: "none",
    borderRadius: 6,
    background: "#0d6efd",
    color: "#ffffff",
    cursor: "pointer",
    fontWeight: 700,
  },
  successButton: {
    padding: "10px 18px",
    border: "none",
    borderRadius: 6,
    background: "#198754",
    color: "#ffffff",
    cursor: "pointer",
    fontWeight: 700,
  },
  dangerButton: {
    padding: "10px 18px",
    border: "none",
    borderRadius: 6,
    background: "#dc3545",
    color: "#ffffff",
    cursor: "pointer",
    fontWeight: 700,
  },
  logoutButton: {
    padding: "9px 15px",
    background: "#dc3545",
    color: "#ffffff",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
  },
  secondaryButton: {
    padding: "9px 15px",
    background: "#ffffff",
    color: "#344054",
    border: "1px solid #cfd4dc",
    borderRadius: 6,
    cursor: "pointer",
    fontWeight: 600,
  },
  dangerLink: {
    border: "none",
    background: "transparent",
    color: "#b42318",
    cursor: "pointer",
    fontWeight: 700,
  },
  success: {
    background: "#d1e7dd",
    color: "#0f5132",
    border: "1px solid #badbcc",
    padding: "12px 15px",
    borderRadius: 6,
    marginBottom: 20,
  },
  error: {
    background: "#f8d7da",
    color: "#842029",
    border: "1px solid #f5c2c7",
    padding: "12px 15px",
    borderRadius: 6,
    marginBottom: 20,
  },
  statusBadge: {
    display: "inline-flex",
    alignItems: "center",
    padding: "6px 10px",
    borderRadius: 999,
    background: "#eef4ff",
    color: "#1d4ed8",
    fontSize: 12,
    fontWeight: 700,
    whiteSpace: "nowrap",
  },
  workflow: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    gap: 8,
    marginBottom: 18,
  },
  workflowStep: {
    padding: "7px 10px",
    border: "1px solid #d0d5dd",
    borderRadius: 999,
    color: "#667085",
    fontSize: 13,
  },
  workflowActive: {
    padding: "7px 10px",
    border: "1px solid #84adff",
    borderRadius: 999,
    color: "#1d4ed8",
    background: "#eef4ff",
    fontSize: 13,
    fontWeight: 700,
  },
  arrow: {
    color: "#98a2b3",
  },
  buttonRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: 10,
    alignItems: "center",
  },
  approvalSummary: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
    gap: 14,
    padding: 16,
    borderRadius: 8,
    background: "#f8fafc",
    border: "1px solid #eaecf0",
    fontSize: 13,
  },
  mono: {
    marginTop: 5,
    wordBreak: "break-all",
    color: "#475467",
    fontFamily: "Consolas, monospace",
  },
  stepCard: {
    padding: 13,
    border: "1px solid #eaecf0",
    borderRadius: 8,
    marginBottom: 10,
  },
  muted: {
    marginTop: 6,
    color: "#667085",
    fontSize: 13,
  },
  commentBox: {
    marginTop: 8,
    padding: 9,
    borderRadius: 6,
    background: "#f8fafc",
    fontSize: 13,
  },
};
