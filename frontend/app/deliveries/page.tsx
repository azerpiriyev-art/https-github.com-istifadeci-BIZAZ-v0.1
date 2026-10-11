"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = "http://127.0.0.1:8001";
const TOKEN_KEY = "bizaz_token";

type User = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
};

type Company = {
  id: string;
  name?: string;
  legal_name?: string;
  role: string;
};

type MeResponse = {
  status: string;
  user: User;
  company: Company | null;
};

type Member = {
  id: string;
  full_name: string;
  role: string;
};

type Product = {
  id: string;
  name: string;
  sku: string | null;
  unit: string;
  is_active: boolean;
};

type PurchaseOrderItem = {
  id: string;
  purchase_order_id: string;
  product_id: string;
  quantity: number | string;
  unit: string;
  unit_price: number | string;
  line_total: number | string;
};

type PurchaseOrder = {
  id: string;
  order_number: string;
  status: string;
  supplier_id: string;
  currency: string;
  total_amount: number | string;
  items: PurchaseOrderItem[];
};

type DeliveryItem = {
  id: string;
  delivery_id: string;
  purchase_order_id: string;
  purchase_order_item_id: string;
  quantity_delivered: number | string;
  notes: string | null;
};

type Delivery = {
  id: string;
  company_id: string;
  purchase_order_id: string;
  supplier_id: string;
  delivery_number: string;
  status: string;
  scheduled_date: string | null;
  dispatched_at: string | null;
  delivered_at: string | null;
  received_by: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  items: DeliveryItem[];
};

type PageResponse<T> = {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
};

type MemberResponse = { items: Member[]; total: number };

type DeliveryForm = {
  purchase_order_id: string;
  delivery_number: string;
  scheduled_date: string;
  notes: string;
};

type ItemDraft = {
  purchase_order_item_id: string;
  quantity_delivered: string;
  notes: string;
};

const statusLabels: Record<string, string> = {
  PLANNED: "Planlaşdırılıb",
  DISPATCHED: "Göndərilib",
  IN_TRANSIT: "Yoldadır",
  PARTIALLY_DELIVERED: "Qismən təhvil verilib",
  DELIVERED: "Təhvil verilib",
  CANCELLED: "Ləğv edilib",
};

const allowedTransitions: Record<string, string[]> = {
  PLANNED: ["DISPATCHED", "CANCELLED"],
  DISPATCHED: ["IN_TRANSIT", "CANCELLED"],
  IN_TRANSIT: ["PARTIALLY_DELIVERED", "DELIVERED", "CANCELLED"],
  PARTIALLY_DELIVERED: ["DELIVERED", "CANCELLED"],
  DELIVERED: [],
  CANCELLED: [],
};

const emptyDeliveryForm: DeliveryForm = {
  purchase_order_id: "",
  delivery_number: "",
  scheduled_date: "",
  notes: "",
};

const emptyItemDraft: ItemDraft = {
  purchase_order_item_id: "",
  quantity_delivered: "",
  notes: "",
};

function asNumber(value: number | string | null | undefined): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("az-AZ");
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("az-AZ");
}

function errorMessage(payload: unknown, fallback: string): string {
  if (
    payload &&
    typeof payload === "object" &&
    "detail" in payload
  ) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((entry) =>
          entry && typeof entry === "object" && "msg" in entry
            ? String((entry as { msg?: unknown }).msg ?? "")
            : ""
        )
        .filter(Boolean)
        .join("; ") || fallback;
    }
  }
  return fallback;
}

export default function DeliveriesPage() {
  const router = useRouter();

  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrder[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [company, setCompany] = useState<Company | null>(null);

  const [form, setForm] = useState<DeliveryForm>(emptyDeliveryForm);
  const [itemDraft, setItemDraft] = useState<ItemDraft>(emptyItemDraft);
  const [expandedDeliveryId, setExpandedDeliveryId] = useState<string | null>(null);
  const [statusDrafts, setStatusDrafts] = useState<Record<string, string>>({});
  const [receiverDrafts, setReceiverDrafts] = useState<Record<string, string>>({});

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [itemSaving, setItemSaving] = useState(false);
  const [statusSavingId, setStatusSavingId] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const canWrite = ["OWNER", "ADMIN", "PROCUREMENT"].includes(company?.role || "");

  const approvedOrders = useMemo(
    () => purchaseOrders.filter((order) => order.status === "APPROVED"),
    [purchaseOrders]
  );

  const productById = useMemo(
    () => new Map(products.map((product) => [product.id, product])),
    [products]
  );

  const purchaseOrderById = useMemo(
    () => new Map(purchaseOrders.map((order) => [order.id, order])),
    [purchaseOrders]
  );

  function getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(TOKEN_KEY);
  }

  function redirectToLogin() {
    localStorage.removeItem(TOKEN_KEY);
    router.replace("/login");
  }

  async function apiRequest(path: string, options: RequestInit = {}): Promise<Response> {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      throw new Error("AUTH_REQUIRED");
    }

    const headers = new Headers(options.headers);
    headers.set("Authorization", "Bearer " + token);
    headers.set("Accept", "application/json");
    if (options.body) headers.set("Content-Type", "application/json");

    const response = await fetch(API_URL + path, {
      ...options,
      headers,
      cache: "no-store",
    });

    if (response.status === 401) {
      redirectToLogin();
      throw new Error("UNAUTHORIZED");
    }

    return response;
  }

  async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await apiRequest(path, options);
    let payload: unknown = {};
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }

    if (!response.ok) {
      throw new Error(errorMessage(payload, "Sorğu uğursuz oldu (HTTP " + response.status + ")."));
    }

    return payload as T;
  }

  async function loadAllPages<T>(path: string): Promise<T[]> {
    const first = await requestJson<PageResponse<T>>(path + "?page=1&limit=100");
    const result = Array.isArray(first.items) ? [...first.items] : [];
    const reportedPages = Number(first.pages);
    const pageCount = Number.isFinite(reportedPages)
      ? Math.max(1, Math.floor(reportedPages))
      : 1;

    for (let page = 2; page <= pageCount; page += 1) {
      const next = await requestJson<PageResponse<T>>(
        path + "?page=" + page + "&limit=100"
      );
      if (Array.isArray(next.items)) result.push(...next.items);
    }

    return result;
  }

  async function loadData(showLoading = true) {
    if (showLoading) setLoading(true);
    setError("");

    try {
      const [deliveryRows, orderRows, productPayload, memberPayload, mePayload, companyPayload] =
        await Promise.all([
          loadAllPages<Delivery>("/api/v1/deliveries"),
          loadAllPages<PurchaseOrder>("/api/v1/purchase-orders"),
          requestJson<unknown>("/api/v1/products"),
          requestJson<MemberResponse>("/api/v1/company/members"),
          requestJson<MeResponse>("/api/v1/me"),
          requestJson<{ company: Company }>("/api/v1/company/me"),
        ]);

      let productRows: Product[] = [];
      if (Array.isArray(productPayload)) {
        productRows = productPayload as Product[];
      } else if (
        productPayload &&
        typeof productPayload === "object" &&
        "products" in productPayload &&
        Array.isArray((productPayload as { products?: unknown }).products)
      ) {
        productRows = (productPayload as { products: Product[] }).products;
      } else if (
        productPayload &&
        typeof productPayload === "object" &&
        "items" in productPayload &&
        Array.isArray((productPayload as { items?: unknown }).items)
      ) {
        productRows = (productPayload as { items: Product[] }).items;
      }

      setDeliveries(deliveryRows);
      setPurchaseOrders(orderRows);
      setProducts(productRows);
      setMembers(Array.isArray(memberPayload.items) ? memberPayload.items : []);
      setCurrentUser(mePayload.user || null);
      setCompany(companyPayload.company || mePayload.company || null);
    } catch (err) {
      if (
        err instanceof Error &&
        (err.message === "AUTH_REQUIRED" || err.message === "UNAUTHORIZED")
      ) {
        return;
      }
      console.error("Delivery page load failed:", err);
      setError(
        err instanceof Error
          ? err.message
          : "Çatdırılma məlumatlarını yükləmək mümkün olmadı."
      );
    } finally {
      if (showLoading) setLoading(false);
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    void loadData();
    // The page loads data on entry; refreshes are explicitly triggered after writes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  function handleLogout() {
    redirectToLogin();
  }

  function updateForm<K extends keyof DeliveryForm>(key: K, value: DeliveryForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleCreateDelivery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (!canWrite) {
      setError("Bu əməliyyat üçün OWNER, ADMIN və ya PROCUREMENT rolu tələb olunur.");
      return;
    }
    if (!form.purchase_order_id) {
      setError("Satınalma sifarişi seçilməlidir.");
      return;
    }
    if (!form.delivery_number.trim()) {
      setError("Çatdırılma nömrəsi daxil edilməlidir.");
      return;
    }

    setSaving(true);
    try {
      await requestJson<Delivery>("/api/v1/deliveries", {
        method: "POST",
        body: JSON.stringify({
          purchase_order_id: form.purchase_order_id,
          delivery_number: form.delivery_number.trim(),
          scheduled_date: form.scheduled_date || null,
          notes: form.notes.trim() || null,
        }),
      });
      setForm(emptyDeliveryForm);
      setShowCreateForm(false);
      setSuccess("Çatdırılma uğurla yaradıldı.");
      await loadData(false);
    } catch (err) {
      if (err instanceof Error && ["AUTH_REQUIRED", "UNAUTHORIZED"].includes(err.message)) return;
      setError(err instanceof Error ? err.message : "Çatdırılma yaradılmadı.");
    } finally {
      setSaving(false);
    }
  }

  function recordedQuantity(purchaseOrderItemId: string): number {
    return deliveries.reduce((sum, delivery) => {
      const itemSum = (delivery.items || [])
        .filter((item) => item.purchase_order_item_id === purchaseOrderItemId)
        .reduce((subtotal, item) => subtotal + asNumber(item.quantity_delivered), 0);
      return sum + itemSum;
    }, 0);
  }

  function availableItems(delivery: Delivery): PurchaseOrderItem[] {
    const order = purchaseOrderById.get(delivery.purchase_order_id);
    if (!order) return [];
    const currentIds = new Set((delivery.items || []).map((item) => item.purchase_order_item_id));

    return (order.items || []).filter((item) => {
      if (currentIds.has(item.id)) return false;
      const remaining = asNumber(item.quantity) - recordedQuantity(item.id);
      return remaining > 0.0000001;
    });
  }

  function remainingQuantity(item: PurchaseOrderItem): number {
    return Math.max(0, asNumber(item.quantity) - recordedQuantity(item.id));
  }

  function productLabel(productId: string): string {
    const product = productById.get(productId);
    return product ? product.name + (product.sku ? " (" + product.sku + ")" : "") : productId;
  }

  function purchaseOrderItemUnit(item: PurchaseOrderItem): string {
    const storedUnit = String(item.unit || "").trim();
    const unitIsCorrupted =
      !storedUnit || storedUnit.includes("?") || storedUnit.includes("\uFFFD");

    if (!unitIsCorrupted) return storedUnit;

    // Keep valid historical PO-line units, but use catalog unit as a safe display fallback
    // when old/test data contains replacement characters or question-mark corruption.
    const catalogUnit = productById.get(item.product_id)?.unit?.trim();
    return catalogUnit || storedUnit;
  }

  async function handleAddItem(event: FormEvent<HTMLFormElement>, delivery: Delivery) {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (!canWrite) {
      setError("Bu əməliyyat üçün kifayət qədər səlahiyyətiniz yoxdur.");
      return;
    }
    if (["DELIVERED", "CANCELLED"].includes(delivery.status)) {
      setError("Yekun statuslu çatdırılmaya yeni element əlavə edilə bilməz.");
      return;
    }

    const quantity = Number(itemDraft.quantity_delivered);
    const order = purchaseOrderById.get(delivery.purchase_order_id);
    const orderItem = order?.items.find((item) => item.id === itemDraft.purchase_order_item_id);

    if (!orderItem) {
      setError("Satınalma sifarişinin elementi seçilməlidir.");
      return;
    }
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setError("Çatdırılan miqdar sıfırdan böyük olmalıdır.");
      return;
    }
    if (quantity > remainingQuantity(orderItem) + 0.0000001) {
      setError("Daxil edilən miqdar sifariş üzrə qalan miqdardan çoxdur.");
      return;
    }

    setItemSaving(true);
    try {
      await requestJson<DeliveryItem>(
        "/api/v1/deliveries/" + delivery.id + "/items",
        {
          method: "POST",
          body: JSON.stringify({
            purchase_order_item_id: itemDraft.purchase_order_item_id,
            quantity_delivered: String(itemDraft.quantity_delivered),
            notes: itemDraft.notes.trim() || null,
          }),
        }
      );
      setItemDraft(emptyItemDraft);
      setSuccess("Çatdırılma elementi əlavə edildi.");
      await loadData(false);
    } catch (err) {
      if (err instanceof Error && ["AUTH_REQUIRED", "UNAUTHORIZED"].includes(err.message)) return;
      setError(err instanceof Error ? err.message : "Çatdırılma elementi əlavə edilmədi.");
    } finally {
      setItemSaving(false);
    }
  }

  async function handleStatusUpdate(delivery: Delivery) {
    setError("");
    setSuccess("");

    if (!canWrite) {
      setError("Bu əməliyyat üçün kifayət qədər səlahiyyətiniz yoxdur.");
      return;
    }

    const newStatus = statusDrafts[delivery.id] || allowedTransitions[delivery.status]?.[0] || "";
    if (!newStatus || !allowedTransitions[delivery.status]?.includes(newStatus)) {
      setError("Seçilmiş status bu çatdırılma üçün keçid qaydalarına uyğun deyil.");
      return;
    }

    const payload: { status: string; received_by?: string } = { status: newStatus };
    if (newStatus === "DELIVERED") {
      const receiverId = receiverDrafts[delivery.id] || currentUser?.id || "";
      if (!receiverId || !members.some((member) => member.id === receiverId)) {
        setError("Təhvil alan şəxs seçilməlidir.");
        return;
      }
      payload.received_by = receiverId;
    }

    setStatusSavingId(delivery.id);
    try {
      await requestJson<Delivery>(
        "/api/v1/deliveries/" + delivery.id + "/status",
        {
          method: "POST",
          body: JSON.stringify(payload),
        }
      );
      setSuccess("Çatdırılma statusu yeniləndi.");
      setStatusDrafts((current) => {
        const next = { ...current };
        delete next[delivery.id];
        return next;
      });
      await loadData(false);
    } catch (err) {
      if (err instanceof Error && ["AUTH_REQUIRED", "UNAUTHORIZED"].includes(err.message)) return;
      setError(err instanceof Error ? err.message : "Status dəyişdirilmədi.");
    } finally {
      setStatusSavingId(null);
    }
  }

  const pageStyle = {
    minHeight: "100vh",
    background: "#f5f7fa",
    color: "#172033",
    fontFamily: "Arial, sans-serif",
    padding: "28px 16px 48px",
  } as const;

  const containerStyle = {
    maxWidth: "1180px",
    margin: "0 auto",
  } as const;

  const cardStyle = {
    background: "#fff",
    border: "1px solid #dce2ea",
    borderRadius: "12px",
    padding: "20px",
    marginBottom: "18px",
    boxShadow: "0 2px 6px rgba(20, 35, 60, 0.04)",
  } as const;

  const inputStyle = {
    width: "100%",
    boxSizing: "border-box" as const,
    padding: "10px 12px",
    border: "1px solid #cbd5e1",
    borderRadius: "7px",
    fontSize: "14px",
    background: "#fff",
    color: "#172033",
  } as const;

  const labelStyle = {
    display: "block",
    fontSize: "13px",
    fontWeight: 700,
    marginBottom: "6px",
    color: "#465268",
  } as const;

  const primaryButtonStyle = {
    border: "0",
    borderRadius: "7px",
    padding: "10px 15px",
    background: "#176b4d",
    color: "#fff",
    cursor: "pointer",
    fontWeight: 700,
  } as const;

  const secondaryButtonStyle = {
    border: "1px solid #cbd5e1",
    borderRadius: "7px",
    padding: "9px 13px",
    background: "#fff",
    color: "#172033",
    cursor: "pointer",
    fontWeight: 600,
  } as const;

  if (loading) {
    return (
      <main style={pageStyle}>
        <div style={{ ...containerStyle, paddingTop: "18vh", textAlign: "center" }}>
          <h1>BIZAZ — Çatdırılmalar</h1>
          <p>Çatdırılma məlumatları yüklənir...</p>
        </div>
      </main>
    );
  }

  return (
    <main style={pageStyle}>
      <div style={containerStyle}>
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "16px",
            flexWrap: "wrap",
            marginBottom: "24px",
          }}
        >
          <div>
            <button type="button" onClick={() => router.push("/dashboard")} style={secondaryButtonStyle}>
              ← İdarəetmə paneli
            </button>
            <h1 style={{ fontSize: "30px", margin: "18px 0 6px" }}>Çatdırılmalar</h1>
            <p style={{ color: "#64748b", margin: 0 }}>
              {company?.legal_name || company?.name || "BIZAZ"} — satınalma sifarişlərinin çatdırılma nəzarəti
            </p>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "13px", color: "#64748b", marginBottom: "8px" }}>
              {currentUser?.full_name || "İstifadəçi"} · {company?.role || "—"}
            </div>
            <button type="button" onClick={handleLogout} style={secondaryButtonStyle}>Çıxış</button>
          </div>
        </header>

        {error && (
          <div role="alert" style={{ background: "#fff1f2", color: "#9f1239", border: "1px solid #fecdd3", padding: "12px 14px", borderRadius: "8px", marginBottom: "14px" }}>
            {error}
          </div>
        )}
        {success && (
          <div role="status" style={{ background: "#ecfdf5", color: "#065f46", border: "1px solid #a7f3d0", padding: "12px 14px", borderRadius: "8px", marginBottom: "14px" }}>
            {success}
          </div>
        )}
        {!canWrite && (
          <div style={{ ...cardStyle, color: "#854d0e", background: "#fffbeb" }}>
            Çatdırılmaları yalnız OWNER, ADMIN və PROCUREMENT rolları yarada, dəyişə və elementlərlə tamamlaya bilər. Siz məlumatlara baxış edə bilərsiniz.
          </div>
        )}

        <section style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
            <div>
              <h2 style={{ fontSize: "20px", margin: "0 0 6px" }}>Çatdırılma reyestri</h2>
              <p style={{ color: "#64748b", margin: 0 }}>
                Cəmi {deliveries.length} çatdırılma · {approvedOrders.length} təsdiqlənmiş sifariş
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowCreateForm((value) => !value)}
              disabled={!canWrite || approvedOrders.length === 0}
              style={{ ...primaryButtonStyle, opacity: !canWrite || approvedOrders.length === 0 ? 0.55 : 1, cursor: !canWrite || approvedOrders.length === 0 ? "not-allowed" : "pointer" }}
            >
              {showCreateForm ? "Formanı bağla" : "＋ Yeni çatdırılma"}
            </button>
          </div>

          {approvedOrders.length === 0 && (
            <p style={{ marginTop: "18px", color: "#64748b" }}>
              Çatdırılma yaratmaq üçün ən azı bir APPROVED statuslu satınalma sifarişi olmalıdır.
            </p>
          )}

          {showCreateForm && (
            <form onSubmit={handleCreateDelivery} style={{ marginTop: "20px", paddingTop: "20px", borderTop: "1px solid #e2e8f0" }}>
              <h3 style={{ margin: "0 0 14px", fontSize: "17px" }}>Yeni çatdırılma</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "14px" }}>
                <div>
                  <label htmlFor="delivery-po" style={labelStyle}>Təsdiqlənmiş satınalma sifarişi *</label>
                  <select id="delivery-po" value={form.purchase_order_id} onChange={(event) => updateForm("purchase_order_id", event.target.value)} style={inputStyle} required>
                    <option value="">Sifariş seçin</option>
                    {approvedOrders.map((order) => (
                      <option key={order.id} value={order.id}>
                        {order.order_number} — {asNumber(order.total_amount).toLocaleString("az-AZ")} {order.currency}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="delivery-number" style={labelStyle}>Çatdırılma nömrəsi *</label>
                  <input id="delivery-number" value={form.delivery_number} onChange={(event) => updateForm("delivery_number", event.target.value)} style={inputStyle} maxLength={50} required placeholder="Məsələn: DEL-2026-001" />
                </div>
                <div>
                  <label htmlFor="delivery-date" style={labelStyle}>Planlaşdırılan tarix</label>
                  <input id="delivery-date" type="date" value={form.scheduled_date} onChange={(event) => updateForm("scheduled_date", event.target.value)} style={inputStyle} />
                </div>
                <div>
                  <label htmlFor="delivery-notes" style={labelStyle}>Qeyd</label>
                  <input id="delivery-notes" value={form.notes} onChange={(event) => updateForm("notes", event.target.value)} style={inputStyle} maxLength={2000} placeholder="Əlavə məlumat" />
                </div>
              </div>
              <div style={{ display: "flex", gap: "10px", marginTop: "16px", flexWrap: "wrap" }}>
                <button type="submit" disabled={saving} style={{ ...primaryButtonStyle, opacity: saving ? 0.6 : 1 }}>
                  {saving ? "Saxlanılır..." : "Çatdırılmanı yarat"}
                </button>
                <button type="button" onClick={() => { setShowCreateForm(false); setForm(emptyDeliveryForm); }} style={secondaryButtonStyle}>Ləğv et</button>
              </div>
            </form>
          )}
        </section>

        {deliveries.length === 0 ? (
          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Çatdırılma yoxdur</h2>
            <p style={{ color: "#64748b", marginBottom: 0 }}>Təsdiqlənmiş satınalma sifarişi üzrə yeni çatdırılma yaradıldıqdan sonra məlumatlar burada görünəcək.</p>
          </section>
        ) : (
          deliveries.map((delivery) => {
            const order = purchaseOrderById.get(delivery.purchase_order_id);
            const transitions = allowedTransitions[delivery.status] || [];
            const isExpanded = expandedDeliveryId === delivery.id;
            const options = availableItems(delivery);
            const canAddItems = canWrite && !["DELIVERED", "CANCELLED"].includes(delivery.status);
            const selectedReceiver = receiverDrafts[delivery.id] || currentUser?.id || "";

            return (
              <section key={delivery.id} style={cardStyle}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "16px", flexWrap: "wrap" }}>
                  <div style={{ minWidth: "230px", flex: "1 1 300px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                      <h2 style={{ margin: 0, fontSize: "19px" }}>{delivery.delivery_number}</h2>
                      <span style={{ borderRadius: "999px", padding: "4px 10px", fontSize: "12px", fontWeight: 700, background: delivery.status === "DELIVERED" ? "#dcfce7" : delivery.status === "CANCELLED" ? "#fee2e2" : "#e0f2fe", color: delivery.status === "DELIVERED" ? "#166534" : delivery.status === "CANCELLED" ? "#991b1b" : "#075985" }}>
                        {statusLabels[delivery.status] || delivery.status}
                      </span>
                    </div>
                    <p style={{ color: "#64748b", margin: "8px 0 4px" }}>
                      Satınalma sifarişi: <strong>{order?.order_number || delivery.purchase_order_id}</strong>
                    </p>
                    <p style={{ color: "#64748b", margin: "4px 0" }}>
                      Planlaşdırılan tarix: {formatDate(delivery.scheduled_date)} · Element sayı: {(delivery.items || []).length}
                    </p>
                    {delivery.notes && <p style={{ margin: "8px 0 0" }}>Qeyd: {delivery.notes}</p>}
                    {delivery.delivered_at && <p style={{ color: "#64748b", margin: "6px 0 0" }}>Təhvil vaxtı: {formatDateTime(delivery.delivered_at)}</p>}
                    {delivery.received_by && (
                      <p style={{ color: "#64748b", margin: "6px 0 0" }}>
                        Təhvil alan: {members.find((member) => member.id === delivery.received_by)?.full_name || delivery.received_by}
                      </p>
                    )}
                  </div>

                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <button type="button" onClick={() => { setExpandedDeliveryId(isExpanded ? null : delivery.id); setItemDraft(emptyItemDraft); }} style={secondaryButtonStyle}>
                      {isExpanded ? "Detalları bağla" : "Detallar / elementlər"}
                    </button>
                  </div>
                </div>

                {transitions.length > 0 && (
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: "12px", alignItems: "end", marginTop: "18px", paddingTop: "16px", borderTop: "1px solid #edf0f4" }}>
                    <div>
                      <label htmlFor={"status-" + delivery.id} style={labelStyle}>Növbəti status</label>
                      <select
                        id={"status-" + delivery.id}
                        value={statusDrafts[delivery.id] || ""}
                        onChange={(event) => setStatusDrafts((current) => ({ ...current, [delivery.id]: event.target.value }))}
                        style={inputStyle}
                        disabled={!canWrite || statusSavingId === delivery.id}
                      >
                        <option value="">Status seçin</option>
                        {transitions.map((status) => <option key={status} value={status}>{statusLabels[status] || status}</option>)}
                      </select>
                    </div>
                    {(statusDrafts[delivery.id] || "") === "DELIVERED" && (
                      <div>
                        <label htmlFor={"receiver-" + delivery.id} style={labelStyle}>Təhvil alan şəxs *</label>
                        <select
                          id={"receiver-" + delivery.id}
                          value={selectedReceiver}
                          onChange={(event) => setReceiverDrafts((current) => ({ ...current, [delivery.id]: event.target.value }))}
                          style={inputStyle}
                          disabled={!canWrite || statusSavingId === delivery.id}
                          required
                        >
                          <option value="">Şirkət üzvü seçin</option>
                          {members.map((member) => <option key={member.id} value={member.id}>{member.full_name} — {member.role}</option>)}
                        </select>
                      </div>
                    )}
                    <div>
                      <button
                        type="button"
                        disabled={!canWrite || !statusDrafts[delivery.id] || statusSavingId === delivery.id}
                        onClick={() => void handleStatusUpdate(delivery)}
                        style={{ ...primaryButtonStyle, opacity: !canWrite || !statusDrafts[delivery.id] || statusSavingId === delivery.id ? 0.55 : 1, cursor: !canWrite || !statusDrafts[delivery.id] || statusSavingId === delivery.id ? "not-allowed" : "pointer" }}
                      >
                        {statusSavingId === delivery.id ? "Yenilənir..." : "Statusu yenilə"}
                      </button>
                    </div>
                  </div>
                )}

                {isExpanded && (
                  <div style={{ marginTop: "18px", paddingTop: "18px", borderTop: "1px solid #e2e8f0" }}>
                    <h3 style={{ margin: "0 0 12px", fontSize: "17px" }}>Çatdırılma elementləri</h3>
                    {(delivery.items || []).length === 0 ? (
                      <p style={{ color: "#64748b" }}>Hələ heç bir sifariş elementi əlavə edilməyib.</p>
                    ) : (
                      <div style={{ overflowX: "auto" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
                          <thead>
                            <tr style={{ textAlign: "left", background: "#f8fafc" }}>
                              <th style={{ padding: "10px", borderBottom: "1px solid #e2e8f0" }}>Məhsul</th>
                              <th style={{ padding: "10px", borderBottom: "1px solid #e2e8f0" }}>Çatdırılan miqdar</th>
                              <th style={{ padding: "10px", borderBottom: "1px solid #e2e8f0" }}>Qeyd</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(delivery.items || []).map((item) => {
                              const poItem = order?.items.find((entry) => entry.id === item.purchase_order_item_id);
                              return (
                                <tr key={item.id}>
                                  <td style={{ padding: "10px", borderBottom: "1px solid #edf0f4" }}>{poItem ? productLabel(poItem.product_id) : item.purchase_order_item_id}</td>
                                  <td style={{ padding: "10px", borderBottom: "1px solid #edf0f4", whiteSpace: "nowrap" }}>{asNumber(item.quantity_delivered).toLocaleString("az-AZ")} {poItem ? purchaseOrderItemUnit(poItem) : ""}</td>
                                  <td style={{ padding: "10px", borderBottom: "1px solid #edf0f4" }}>{item.notes || "—"}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {canAddItems && (
                      <form onSubmit={(event) => void handleAddItem(event, delivery)} style={{ marginTop: "18px", padding: "16px", background: "#f8fafc", borderRadius: "9px" }}>
                        <h4 style={{ margin: "0 0 12px" }}>Sifariş elementini əlavə et</h4>
                        {options.length === 0 ? (
                          <p style={{ marginBottom: 0, color: "#64748b" }}>Əlavə edilə bilən element yoxdur və ya sifariş üzrə qalan miqdar yoxdur.</p>
                        ) : (
                          <>
                            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px" }}>
                              <div>
                                <label htmlFor={"po-item-" + delivery.id} style={labelStyle}>Sifariş elementi *</label>
                                <select
                                  id={"po-item-" + delivery.id}
                                  value={itemDraft.purchase_order_item_id}
                                  onChange={(event) => setItemDraft((current) => ({ ...current, purchase_order_item_id: event.target.value, quantity_delivered: "" }))}
                                  style={inputStyle}
                                  required
                                >
                                  <option value="">Məhsul seçin</option>
                                  {options.map((item) => (
                                    <option key={item.id} value={item.id}>
                                      {productLabel(item.product_id)} · qalıq {remainingQuantity(item).toLocaleString("az-AZ")} {purchaseOrderItemUnit(item)}
                                    </option>
                                  ))}
                                </select>
                              </div>
                              <div>
                                <label htmlFor={"qty-" + delivery.id} style={labelStyle}>Çatdırılan miqdar *</label>
                                <input
                                  id={"qty-" + delivery.id}
                                  type="number"
                                  min="0.0001"
                                  step="0.0001"
                                  value={itemDraft.quantity_delivered}
                                  onChange={(event) => setItemDraft((current) => ({ ...current, quantity_delivered: event.target.value }))}
                                  style={inputStyle}
                                  required
                                />
                              </div>
                              <div>
                                <label htmlFor={"item-note-" + delivery.id} style={labelStyle}>Qeyd</label>
                                <input
                                  id={"item-note-" + delivery.id}
                                  value={itemDraft.notes}
                                  onChange={(event) => setItemDraft((current) => ({ ...current, notes: event.target.value }))}
                                  style={inputStyle}
                                  maxLength={2000}
                                />
                              </div>
                            </div>
                            {itemDraft.purchase_order_item_id && (
                              <p style={{ color: "#64748b", fontSize: "13px", margin: "10px 0 0" }}>
                                Sifariş üzrə qalan miqdar: {remainingQuantity(order?.items.find((item) => item.id === itemDraft.purchase_order_item_id) || { quantity: 0, id: "", purchase_order_id: "", product_id: "", unit: "", unit_price: 0, line_total: 0 }).toLocaleString("az-AZ")}
                              </p>
                            )}
                            <button type="submit" disabled={itemSaving} style={{ ...primaryButtonStyle, marginTop: "12px", opacity: itemSaving ? 0.6 : 1 }}>
                              {itemSaving ? "Əlavə olunur..." : "Elementi əlavə et"}
                            </button>
                          </>
                        )}
                      </form>
                    )}
                  </div>
                )}
              </section>
            );
          })
        )}

        <p style={{ color: "#64748b", fontSize: "12px", marginTop: "24px" }}>
          Miqdar və status qaydaları backend tərəfindən yenidən yoxlanılır. Ləğv edilmiş çatdırılmalardakı qeydə alınmış miqdarlar sifariş üzrə ümumi çatdırılma hesabında saxlanılır.
        </p>
      </div>
    </main>
  );
}
