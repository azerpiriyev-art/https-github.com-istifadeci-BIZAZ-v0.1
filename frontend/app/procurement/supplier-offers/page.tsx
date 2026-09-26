"use client";

import { useEffect, useState } from "react";

const API_URL = "http://127.0.0.1:8001";

type Supplier = {
  id: string;
  name: string;
  tax_id: string | null;
  contact_person: string | null;
  phone: string | null;
  email: string | null;
  is_active: boolean;
};

type PurchaseRequest = {
  id: string;
  request_number: string;
  request_date: string | null;
  status: string;
  items: PurchaseRequestItem[];
};

type PurchaseRequestItem = {
  id: string;
  purchase_request_id: string;
  product_id: string;
  quantity: number | string;
  unit: string;
  required_date: string | null;
  specifications: string | null;
  notes: string | null;
};

type OfferItem = {
  purchase_request_item_id: string;
  product_id: string;
  quantity: string;
  unit: string;
  unit_price: string;
  vat_rate: string;
  delivery_days: string;
  notes: string;
};

function emptyOfferItem(item: PurchaseRequestItem): OfferItem {
  return {
    purchase_request_item_id: item.id,
    product_id: item.product_id,
    quantity: String(item.quantity ?? ""),
    unit: item.unit || "",
    unit_price: "",
    vat_rate: "18",
    delivery_days: "",
    notes: "",
  };
}

export default function SupplierOffersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [selectedRequestId, setSelectedRequestId] = useState("");

  const [supplierId, setSupplierId] = useState("");
  const [offerNumber, setOfferNumber] = useState("");
  const [offerDate, setOfferDate] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [validUntil, setValidUntil] = useState("");
  const [currency, setCurrency] = useState("AZN");
  const [status, setStatus] = useState("DRAFT");
  const [notes, setNotes] = useState("");

  const [items, setItems] = useState<OfferItem[]>([]);

  const [loading, setLoading] = useState(true);
  const [loadingRequest, setLoadingRequest] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    void loadInitialData();
  }, []);

  async function getToken() {
    const token = localStorage.getItem("bizaz_token");

    if (!token) {
      throw new Error("Sistemə daxil olmaq tələb olunur.");
    }

    return token;
  }

  async function loadInitialData() {
    setLoading(true);
    setError("");

    try {
      const token = await getToken();

      const [supplierResponse, requestResponse] = await Promise.all([
        fetch(`${API_URL}/api/v1/suppliers`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }),
        fetch(`${API_URL}/api/v1/procurement/purchase-requests`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }),
      ]);

      const supplierData = await supplierResponse.json();
      const requestData = await requestResponse.json();

      if (!supplierResponse.ok) {
        throw new Error(
          supplierData.detail || "Təchizatçılar yüklənmədi."
        );
      }

      if (!requestResponse.ok) {
        throw new Error(
          requestData.detail || "Satınalma sorğuları yüklənmədi."
        );
      }

      setSuppliers(
        Array.isArray(supplierData)
          ? supplierData.filter((supplier: Supplier) => supplier.is_active)
          : []
      );

      setRequests(Array.isArray(requestData) ? requestData : []);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Məlumatların yüklənməsi zamanı xəta baş verdi."
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadRequestDetail(requestId: string) {
    setSelectedRequestId(requestId);
    setError("");
    setMessage("");

    if (!requestId) {
      setItems([]);
      return;
    }

    setLoadingRequest(true);

    try {
      const token = await getToken();

      const response = await fetch(
        `${API_URL}/api/v1/procurement/purchase-requests/${requestId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Satınalma sorğusu yüklənmədi."
        );
      }

      const requestItems: PurchaseRequestItem[] = Array.isArray(data.items)
        ? data.items
        : [];

      setItems(requestItems.map(emptyOfferItem));

      setMessage(
        `${data.request_number || "Satınalma sorğusu"} seçildi.`
      );
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Satınalma sorğusu yüklənmədi."
      );
      setItems([]);
    } finally {
      setLoadingRequest(false);
    }
  }

  function updateItem(
    index: number,
    field: keyof OfferItem,
    value: string
  ) {
    setItems((current) =>
      current.map((item, itemIndex) =>
        itemIndex === index
          ? {
              ...item,
              [field]: value,
            }
          : item
      )
    );
  }


    async function submitOffer() {
    setError("");
    setMessage("");

    if (!selectedRequestId) {
      setError("Satınalma sorğusu seçilməlidir.");
      return;
    }

    if (!supplierId) {
      setError("Təchizatçı seçilməlidir.");
      return;
    }

    if (!offerNumber.trim()) {
      setError("Təklif nömrəsi daxil edilməlidir.");
      return;
    }

    if (items.length === 0) {
      setError("Ən azı bir təklif sətri olmalıdır.");
      return;
    }

    if (items.some((item) => !item.unit_price.trim())) {
      setError("Bütün sətirlər üzrə vahid qiymət daxil edilməlidir.");
      return;
    }

    try {
      const token = await getToken();

      const payload = {
        purchase_request_id: selectedRequestId,
        supplier_id: supplierId,
        offer_number: offerNumber.trim(),
        offer_date: offerDate || null,
        valid_until: validUntil || null,
        currency,
        status,
        notes: notes.trim() || null,
        items: items.map((item) => ({
          purchase_request_item_id: item.purchase_request_item_id,
          product_id: item.product_id,
          quantity: Number(item.quantity),
          unit: item.unit,
          unit_price: Number(item.unit_price),
          vat_rate: Number(item.vat_rate),
          delivery_days: item.delivery_days
            ? Number(item.delivery_days)
            : null,
          notes: item.notes.trim() || null,
        })),
      };

      const response = await fetch(
        `${API_URL}/api/v1/procurement/supplier-offers`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(payload),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Təchizatçı təklifi yaradılmadı."
        );
      }

      setMessage(
        `Təchizatçı təklifi yaradıldı — ${data.offer_number || offerNumber}.`
      );
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Təchizatçı təklifi yaradılmadı."
      );
    }
  }




  const selectedRequest = requests.find(
    (request) => request.id === selectedRequestId
  );

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <header style={styles.header}>
          <div style={styles.eyebrow}>BIZAZ • PROCUREMENT</div>
          <h1 style={styles.title}>Təchizatçı təklifi</h1>
          <p style={styles.subtitle}>
            Satınalma sorğusuna əsasən təchizatçı təklifinin hazırlanması
          </p>
        </header>

        <div style={styles.steps}>
          <span>1. Satınalma sorğusu</span>
          <span>→</span>
          <span style={styles.stepActive}>2. Təchizatçı təklifi</span>
          <span>→</span>
          <span>3. Müqayisə</span>
          <span>→</span>
          <span>4. Seçim</span>
          <span>→</span>
          <span>5. Satınalma sifarişi</span>
        </div>

        {message && <div style={styles.success}>{message}</div>}
        {error && <div style={styles.error}>{error}</div>}

        {loading ? (
          <section style={styles.card}>
            Məlumatlar yüklənir...
          </section>
        ) : (
          <>
            <section style={styles.card}>
              <div style={styles.sectionHeader}>
                <h2 style={styles.sectionTitle}>
                  Təklif məlumatları
                </h2>
              </div>

              <div style={styles.grid3}>
                <label style={styles.label}>
                  Satınalma sorğusu
                  <select
                    value={selectedRequestId}
                    onChange={(e) =>
                      void loadRequestDetail(e.target.value)
                    }
                    style={styles.input}
                  >
                    <option value="">
                      Satınalma sorğusu seçin
                    </option>

                    {requests.map((request) => (
                      <option key={request.id} value={request.id}>
                        {request.request_number} — {request.status}
                      </option>
                    ))}
                  </select>
                </label>

                <label style={styles.label}>
                  Təchizatçı
                  <select
                    value={supplierId}
                    onChange={(e) => setSupplierId(e.target.value)}
                    style={styles.input}
                  >
                    <option value="">
                      Təchizatçı seçin
                    </option>

                    {suppliers.map((supplier) => (
                      <option key={supplier.id} value={supplier.id}>
                        {supplier.name}
                        {supplier.tax_id
                          ? ` — ${supplier.tax_id}`
                          : ""}
                      </option>
                    ))}
                  </select>
                </label>

                <label style={styles.label}>
                  Təklif №
                  <input
                    value={offerNumber}
                    onChange={(e) => setOfferNumber(e.target.value)}
                    style={styles.input}
                    placeholder="SO-2026-001"
                  />
                </label>

                <label style={styles.label}>
                  Təklif tarixi
                  <input
                    type="date"
                    value={offerDate}
                    onChange={(e) => setOfferDate(e.target.value)}
                    style={styles.input}
                  />
                </label>

                <label style={styles.label}>
                  Qüvvədə olma tarixi
                  <input
                    type="date"
                    value={validUntil}
                    onChange={(e) => setValidUntil(e.target.value)}
                    style={styles.input}
                  />
                </label>

                <label style={styles.label}>
                  Valyuta
                  <select
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    style={styles.input}
                  >
                    <option value="AZN">AZN</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                  </select>
                </label>
              </div>

              <div style={{ marginTop: 16 }}>
                <label style={styles.label}>
                  Status
                  <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    style={styles.input}
                  >
                    <option value="DRAFT">Qaralama</option>
                    <option value="SUBMITTED">Təqdim edilmiş</option>
                  </select>
                </label>
              </div>

              <div style={{ marginTop: 16 }}>
                <label style={styles.label}>
                  Qeyd
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    rows={3}
                    style={styles.textarea}
                    placeholder="Təklif haqqında əlavə qeyd..."
                  />
                </label>
              </div>
            </section>

            <section style={styles.card}>
              <div style={styles.sectionHeader}>
                <div>
                  <h2 style={styles.sectionTitle}>
                    Təklif sətirləri
                  </h2>

                  {selectedRequest && (
                    <div style={styles.requestInfo}>
                      Sorğu:{" "}
                      <strong>{selectedRequest.request_number}</strong>
                    </div>
                  )}
                </div>
              </div>

              {!selectedRequestId ? (
                <div style={styles.emptyState}>
                  Əvvəlcə satınalma sorğusu seçin.
                </div>
              ) : loadingRequest ? (
                <div style={styles.emptyState}>
                  Sorğu sətirləri yüklənir...
                </div>
              ) : items.length === 0 ? (
                <div style={styles.emptyState}>
                  Bu satınalma sorğusunda sətir yoxdur.
                </div>
              ) : (
                items.map((item, index) => (
                  <div key={item.purchase_request_item_id} style={styles.itemCard}>
                    <div style={styles.itemNumber}>
                      Sətir {index + 1}
                    </div>

                    <div style={styles.grid4}>
                      <label style={styles.label}>
                        Məhsul ID
                        <input
                          value={item.product_id}
                          readOnly
                          style={styles.inputReadonly}
                        />
                      </label>

                      <label style={styles.label}>
                        Miqdar
                        <input
                          value={item.quantity}
                          onChange={(e) =>
                            updateItem(
                              index,
                              "quantity",
                              e.target.value
                            )
                          }
                          type="number"
                          min="0"
                          step="0.0001"
                          style={styles.input}
                        />
                      </label>

                      <label style={styles.label}>
                        Vahid
                        <input
                          value={item.unit}
                          readOnly
                          style={styles.inputReadonly}
                        />
                      </label>

                      <label style={styles.label}>
                        Vahid qiymət
                        <input
                          value={item.unit_price}
                          onChange={(e) =>
                            updateItem(
                              index,
                              "unit_price",
                              e.target.value
                            )
                          }
                          type="number"
                          min="0"
                          step="0.0001"
                          style={styles.input}
                          placeholder="0.00"
                        />
                      </label>
                    </div>

                    <div style={styles.grid3Item}>
                      <label style={styles.label}>
                        ƏDV %
                        <input
                          value={item.vat_rate}
                          onChange={(e) =>
                            updateItem(
                              index,
                              "vat_rate",
                              e.target.value
                            )
                          }
                          type="number"
                          min="0"
                          max="100"
                          step="0.01"
                          style={styles.input}
                        />
                      </label>

                      <label style={styles.label}>
                        Çatdırılma müddəti, gün
                        <input
                          value={item.delivery_days}
                          onChange={(e) =>
                            updateItem(
                              index,
                              "delivery_days",
                              e.target.value
                            )
                          }
                          type="number"
                          min="0"
                          step="1"
                          style={styles.input}
                        />
                      </label>

                      <label style={styles.label}>
                        Qeyd
                        <input
                          value={item.notes}
                          onChange={(e) =>
                            updateItem(
                              index,
                              "notes",
                              e.target.value
                            )
                          }
                          style={styles.input}
                          placeholder="Sətir qeydi..."
                        />
                      </label>
                    </div>
                  </div>
                ))
              )}
            </section>

            <section style={styles.card}>
  <div style={styles.actions}>
    <button
      type="button"
      onClick={() => void submitOffer()}
      disabled={loading || loadingRequest || items.length === 0}
      style={styles.primaryButton}
    >
      Təklifi yarat
    </button>
  </div>
</section>
          </>
        )}
      </div>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: "#f5f7fb",
    padding: 32,
    color: "#172033",
  },
  container: {
    maxWidth: 1400,
    margin: "0 auto",
  },
  header: {
    marginBottom: 20,
  },
  eyebrow: {
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: 1,
    color: "#667085",
    marginBottom: 6,
  },
  title: {
    margin: 0,
    fontSize: 30,
  },
  subtitle: {
    margin: "8px 0 0",
    color: "#667085",
  },
  steps: {
    display: "flex",
    gap: 10,
    alignItems: "center",
    flexWrap: "wrap",
    padding: "14px 18px",
    background: "#fff",
    border: "1px solid #e4e7ec",
    borderRadius: 10,
    marginBottom: 20,
    color: "#667085",
    fontSize: 14,
  },
  stepActive: {
    color: "#175cd3",
    fontWeight: 700,
  },
  success: {
    padding: 14,
    marginBottom: 18,
    background: "#ecfdf3",
    border: "1px solid #abefc6",
    borderRadius: 8,
    color: "#067647",
  },
  error: {
    padding: 14,
    marginBottom: 18,
    background: "#fef3f2",
    border: "1px solid #fecdca",
    borderRadius: 8,
    color: "#b42318",
  },
  card: {
    background: "#fff",
    border: "1px solid #e4e7ec",
    borderRadius: 12,
    padding: 24,
    marginBottom: 20,
  },
  sectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 16,
    marginBottom: 18,
  },
  sectionTitle: {
    margin: 0,
    fontSize: 20,
  },
  grid3: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: 18,
  },
  grid3Item: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr 2fr",
    gap: 14,
    marginTop: 14,
  },
  label: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    fontWeight: 600,
    fontSize: 14,
  },
  input: {
    width: "100%",
    boxSizing: "border-box",
    padding: "10px 12px",
    border: "1px solid #d0d5dd",
    borderRadius: 8,
    fontSize: 14,
    background: "#fff",
    color: "#172033",
  },
  inputReadonly: {
    width: "100%",
    boxSizing: "border-box",
    padding: "10px 12px",
    border: "1px solid #d0d5dd",
    borderRadius: 8,
    fontSize: 14,
    background: "#f9fafb",
    color: "#667085",
  },
  textarea: {
    width: "100%",
    boxSizing: "border-box",
    padding: "10px 12px",
    border: "1px solid #d0d5dd",
    borderRadius: 8,
    fontSize: 14,
    resize: "vertical",
    fontFamily: "inherit",
  },
  itemCard: {
    border: "1px solid #eaecf0",
    borderRadius: 10,
    padding: 18,
    marginBottom: 14,
  },
  itemNumber: {
    fontSize: 13,
    color: "#667085",
    fontWeight: 700,
    marginBottom: 14,
  },
  requestInfo: {
    marginTop: 5,
    color: "#667085",
    fontSize: 13,
  },
  emptyState: {
    padding: 20,
    border: "1px dashed #d0d5dd",
    borderRadius: 8,
    color: "#667085",
    textAlign: "center",
  },
  infoBox: {
    padding: 14,
    background: "#eff8ff",
    border: "1px solid #b2ddff",
    borderRadius: 8,
    color: "#175cd3",
    fontSize: 14,
  },
};
