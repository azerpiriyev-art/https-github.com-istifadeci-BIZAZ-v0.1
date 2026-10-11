"use client";

import { useCallback, useEffect, useMemo, useState, type CSSProperties, type FormEvent } from "react";
import { useRouter } from "next/navigation";

const API_URL = "http://127.0.0.1:8001";
const TOKEN_KEY = "bizaz_token";

type ApiError = Error & { status?: number };

type Delivery = {
  id: string;
  purchase_order_id: string;
  supplier_id: string;
  delivery_number: string;
  status: string;
  delivered_at: string | null;
};

type DeliveryList = {
  items: Delivery[];
  total: number;
  page: number;
  limit: number;
  pages: number;
};

type Review = {
  id: string;
  company_id: string;
  purchase_order_id: string;
  supplier_id: string;
  reviewer_user_id: string;
  rating: number;
  comment: string | null;
  created_at: string;
  updated_at: string;
};

type ReviewList = {
  items: Review[];
  total: number;
  page: number;
  limit: number;
  pages: number;
  average_rating: number | null;
  rating_count: number;
};

type SupplierStats = {
  average_rating: number | null;
  rating_count: number;
};

type CurrentUserResponse = {
  user: { id: string; is_active: boolean };
  company: { id: string; role: string } | null;
};

type ReviewEntry = {
  delivery: Delivery;
  review: Review | null;
  stats: SupplierStats;
};

async function apiJson<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
    cache: "no-store",
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message =
      typeof payload?.detail === "string"
        ? payload.detail
        : "Sorğunu yerinə yetirmək mümkün olmadı.";
    const error = new Error(message) as ApiError;
    error.status = response.status;
    throw error;
  }

  return payload as T;
}

export default function ReviewsPage() {
  const router = useRouter();
  const [entries, setEntries] = useState<ReviewEntry[]>([]);
  const [selectedPurchaseOrder, setSelectedPurchaseOrder] = useState("");
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [currentUserId, setCurrentUserId] = useState("");
  const [currentRole, setCurrentRole] = useState("");

  const loadData = useCallback(async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      router.replace("/login");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const me = await apiJson<CurrentUserResponse>("/api/v1/me", token);
      if (!me.user?.is_active) {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
        return;
      }
      setCurrentUserId(me.user.id);
      setCurrentRole(me.company?.role ?? "");

      const firstPage = await apiJson<DeliveryList>(
        "/api/v1/deliveries?page=1&limit=100",
        token,
      );
      const laterPages = firstPage.pages > 1
        ? await Promise.all(
            Array.from({ length: firstPage.pages - 1 }, (_, index) =>
              apiJson<DeliveryList>(
                `/api/v1/deliveries?page=${index + 2}&limit=100`,
                token,
              ),
            ),
          )
        : [];
      const deliveries = [
        ...firstPage.items,
        ...laterPages.flatMap((page) => page.items),
      ];

      const latestDeliveredByOrder = new Map<string, Delivery>();
      for (const delivery of deliveries) {
        if (
          delivery.status === "DELIVERED" &&
          !latestDeliveredByOrder.has(delivery.purchase_order_id)
        ) {
          latestDeliveredByOrder.set(delivery.purchase_order_id, delivery);
        }
      }
      const completed = Array.from(latestDeliveredByOrder.values());

      const supplierIds = Array.from(
        new Set(completed.map((delivery) => delivery.supplier_id)),
      );
      const statsPairs = await Promise.all(
        supplierIds.map(async (supplierId) => {
          const data = await apiJson<ReviewList>(
            `/api/v1/suppliers/${supplierId}/reviews?page=1&limit=1`,
            token,
          );
          return [
            supplierId,
            {
              average_rating: data.average_rating,
              rating_count: data.rating_count,
            } satisfies SupplierStats,
          ] as const;
        }),
      );
      const statsBySupplier = new Map(statsPairs);

      const nextEntries = await Promise.all(
        completed.map(async (delivery): Promise<ReviewEntry> => {
          let review: Review | null = null;
          try {
            review = await apiJson<Review>(
              `/api/v1/purchase-orders/${delivery.purchase_order_id}/review`,
              token,
            );
          } catch (loadError) {
            if ((loadError as ApiError).status !== 404) {
              throw loadError;
            }
          }

          return {
            delivery,
            review,
            stats: statsBySupplier.get(delivery.supplier_id) ?? {
              average_rating: null,
              rating_count: 0,
            },
          };
        }),
      );

      setEntries(nextEntries);
    } catch (loadError) {
      const apiError = loadError as ApiError;
      if (apiError.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
        return;
      }
      setError(apiError.message || "Məlumatları yükləmək mümkün olmadı.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    if (
      !loading &&
      selectedPurchaseOrder &&
      !entries.some(
        (entry) => entry.delivery.purchase_order_id === selectedPurchaseOrder,
      )
    ) {
      setSelectedPurchaseOrder("");
    }
  }, [entries, loading, selectedPurchaseOrder]);

  const pendingEntries = useMemo(
    () => entries.filter((entry) => entry.review === null),
    [entries],
  );
  const reviewedEntries = useMemo(
    () => entries.filter((entry) => entry.review !== null),
    [entries],
  );
  const canWrite = ["OWNER", "ADMIN", "PROCUREMENT"].includes(currentRole);
  const selectedEntry = entries.find(
    (entry) => entry.delivery.purchase_order_id === selectedPurchaseOrder,
  );
  const isEditing = selectedEntry?.review != null;
  const canEditReview = (review: Review) =>
    Date.now() - Date.parse(review.created_at) <= 24 * 60 * 60 * 1000;

  const submitReview = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedEntry || !canWrite) return;

    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      router.replace("/login");
      return;
    }

    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      await apiJson<Review>(
        `/api/v1/purchase-orders/${selectedEntry.delivery.purchase_order_id}/review`,
        token,
        {
          method: isEditing ? "PATCH" : "POST",
          body: JSON.stringify({
            rating,
            comment: comment.trim() || null,
          }),
        },
      );
      setNotice(isEditing ? "Rəy uğurla yeniləndi." : "Rəy uğurla qeydə alındı.");
      setSelectedPurchaseOrder("");
      setRating(5);
      setComment("");
      await loadData();
    } catch (submitError) {
      const apiError = submitError as ApiError;
      if (apiError.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
        return;
      }
      setError(apiError.message || "Rəyi göndərmək mümkün olmadı.");
      if (apiError.status === 409) {
        await loadData();
      }
    } finally {
      setSubmitting(false);
    }
  };

  const cardStyle: CSSProperties = {
    background: "#fff",
    border: "1px solid #ddd",
    borderRadius: 10,
    padding: 18,
    marginBottom: 12,
  };

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: 24 }}>
      <header style={{ marginBottom: 24 }}>
        <button
          type="button"
          onClick={() => router.push("/dashboard")}
          style={{
            border: "1px solid #ccc",
            background: "#fff",
            borderRadius: 6,
            padding: "8px 12px",
            cursor: "pointer",
            marginBottom: 16,
          }}
        >
          ← İdarə panelinə qayıt
        </button>
        <h1 style={{ fontSize: 28, fontWeight: 700 }}>Rəylər və reytinqlər</h1>
        <p style={{ color: "#555", marginTop: 8 }}>
          Tam çatdırılmış sifarişlər üzrə şirkətdaxili təchizatçı qiymətləndirməsi.
        </p>
      </header>

      {error && (
        <p role="alert" style={{ background: "#fff0f0", color: "#a40000", padding: 12, borderRadius: 6 }}>
          {error}
        </p>
      )}
      {notice && (
        <p role="status" style={{ background: "#eef8ee", color: "#176b2c", padding: 12, borderRadius: 6 }}>
          {notice}
        </p>
      )}

      {loading ? (
        <p>Rəylər yüklənir...</p>
      ) : (
        <>
          <section style={{ marginBottom: 32 }}>
            <h2 style={{ fontSize: 20, fontWeight: 650, marginBottom: 14 }}>
              Qiymətləndirilməmiş sifarişlər ({pendingEntries.length})
            </h2>
            {pendingEntries.length === 0 ? (
              <p style={{ color: "#555" }}>
                Hazırda qiymətləndirmə gözləyən tam çatdırılmış sifariş yoxdur.
              </p>
            ) : (
              pendingEntries.map((entry) => (
                <article key={entry.delivery.purchase_order_id} style={cardStyle}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
                    <div>
                      <strong>Sifariş: {entry.delivery.purchase_order_id.slice(0, 8)}</strong>
                      <p style={{ color: "#555", marginTop: 5 }}>
                        Çatdırılma: {entry.delivery.delivery_number}
                      </p>
                      <p style={{ color: "#555", marginTop: 4 }}>
                        Təchizatçı üzrə orta bal: {entry.stats.average_rating ?? "—"} · Rəy sayı: {entry.stats.rating_count}
                      </p>
                    </div>
                    {canWrite ? (
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedPurchaseOrder(entry.delivery.purchase_order_id);
                        setRating(5);
                        setComment("");
                        setError("");
                        setNotice("");
                      }}
                      style={{
                        background: selectedPurchaseOrder === entry.delivery.purchase_order_id ? "#14532d" : "#198754",
                        color: "#fff",
                        border: 0,
                        borderRadius: 6,
                        padding: "10px 14px",
                        cursor: "pointer",
                      }}
                    >
                      {selectedPurchaseOrder === entry.delivery.purchase_order_id ? "Seçildi" : "Təchizatçını qiymətləndir"}
                    </button>
                    ) : (
                      <span style={{ color: "#666" }}>Bu rol ilə rəy yazmaq icazəsi yoxdur.</span>
                    )}
                  </div>
                </article>
              ))
            )}
          </section>

          {selectedEntry && canWrite && (
            (!selectedEntry.review || (
              selectedEntry.review.reviewer_user_id === currentUserId &&
              canEditReview(selectedEntry.review)
            )) && (
            <section style={{ ...cardStyle, marginBottom: 32 }}>
              <h2 style={{ fontSize: 20, fontWeight: 650, marginBottom: 14 }}>
                {isEditing ? "Rəyi redaktə et" : "Sifariş üzrə rəy"}
              </h2>
              <form onSubmit={submitReview}>
                <label htmlFor="review-rating" style={{ display: "block", fontWeight: 600, marginBottom: 6 }}>
                  Ümumi bal (1–5)
                </label>
                <select
                  id="review-rating"
                  value={rating}
                  onChange={(event) => setRating(Number(event.target.value))}
                  style={{ padding: 10, minWidth: 180, border: "1px solid #bbb", borderRadius: 6, marginBottom: 16 }}
                >
                  {[5, 4, 3, 2, 1].map((value) => (
                    <option key={value} value={value}>{value} / 5</option>
                  ))}
                </select>

                <label htmlFor="review-comment" style={{ display: "block", fontWeight: 600, marginBottom: 6 }}>
                  Şərh (könüllü, maksimum 2000 simvol)
                </label>
                <textarea
                  id="review-comment"
                  value={comment}
                  onChange={(event) => setComment(event.target.value.slice(0, 2000))}
                  rows={4}
                  maxLength={2000}
                  placeholder="Təchizatçının işi, keyfiyyət və çatdırılma barədə qeyd..."
                  style={{ width: "100%", boxSizing: "border-box", padding: 10, border: "1px solid #bbb", borderRadius: 6, marginBottom: 8 }}
                />
                <p style={{ textAlign: "right", fontSize: 12, color: "#666", marginBottom: 16 }}>
                  {comment.length}/2000
                </p>

                <div style={{ display: "flex", gap: 10 }}>
                  <button
                    type="submit"
                    disabled={submitting}
                    style={{ background: "#198754", color: "#fff", border: 0, borderRadius: 6, padding: "10px 16px", cursor: submitting ? "wait" : "pointer", opacity: submitting ? 0.7 : 1 }}
                  >
                    {submitting ? "Göndərilir..." : isEditing ? "Dəyişiklikləri saxla" : "Rəyi göndər"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedPurchaseOrder("")}
                    style={{ background: "#f3f3f3", border: "1px solid #ccc", borderRadius: 6, padding: "10px 16px", cursor: "pointer" }}
                  >
                    Ləğv et
                  </button>
                </div>
              </form>
            </section>
          )
          )}

          <section>
            <h2 style={{ fontSize: 20, fontWeight: 650, marginBottom: 14 }}>
              Yazılmış rəylər ({reviewedEntries.length})
            </h2>
            {reviewedEntries.length === 0 ? (
              <p style={{ color: "#555" }}>Hələ rəy yazılmayıb.</p>
            ) : (
              reviewedEntries.map((entry) => (
                <article key={entry.review!.id} style={cardStyle}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
                    <div>
                      <strong>Sifariş: {entry.delivery.purchase_order_id.slice(0, 8)}</strong>
                      <p style={{ color: "#555", marginTop: 5 }}>
                        Çatdırılma: {entry.delivery.delivery_number}
                      </p>
                      {entry.review!.comment && (
                        <p style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>{entry.review!.comment}</p>
                      )}
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <strong>{entry.review!.rating} / 5</strong>
                      <p style={{ color: "#555", fontSize: 12, marginTop: 5 }}>
                        Təchizatçı ortalaması: {entry.stats.average_rating ?? "—"}
                      </p>
                      {canWrite &&
                        entry.review!.reviewer_user_id === currentUserId &&
                        canEditReview(entry.review!) && (
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedPurchaseOrder(entry.delivery.purchase_order_id);
                              setRating(entry.review!.rating);
                              setComment(entry.review!.comment ?? "");
                              setError("");
                              setNotice("");
                            }}
                            style={{ marginTop: 10, background: "#f3f3f3", border: "1px solid #ccc", borderRadius: 6, padding: "7px 10px", cursor: "pointer" }}
                          >
                            Rəyi redaktə et
                          </button>
                        )}
                    </div>
                  </div>
                </article>
              ))
            )}
          </section>
        </>
      )}
    </main>
  );
}
