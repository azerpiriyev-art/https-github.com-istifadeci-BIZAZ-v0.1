"use client";

import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";
const TOKEN_KEY = "bizaz_token";

type ApiError = Error & { status?: number };

type NotificationItem = {
  id: string;
  event_type: string;
  title: string;
  body: string;
  source_entity_type: string;
  source_entity_id: string;
  created_at: string;
  read_at: string | null;
};

type NotificationPage = {
  items: NotificationItem[];
  total: number;
  page: number;
  limit: number;
  pages: number;
};

type UnreadCount = { count: number };

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

function eventLabel(eventType: string): string {
  const labels: Record<string, string> = {
    APPROVAL_ACTION_REQUIRED: "Təsdiq tələb olunur",
    APPROVAL_DECISION_RECORDED: "Təsdiq qərarı",
    PURCHASE_REQUEST_STATUS_CHANGED: "Satınalma sorğusu",
    SUPPLIER_OFFER_SUBMITTED: "Təchizatçı təklifi",
    PURCHASE_ORDER_STATUS_CHANGED: "Satınalma sifarişi",
    DELIVERY_STATUS_CHANGED: "Çatdırılma",
    PAYMENT_STATUS_CHANGED: "Ödəniş",
  };
  return labels[eventType] ?? "Bildiriş";
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("az-AZ", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

export default function NotificationsPage() {
  const router = useRouter();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [markingId, setMarkingId] = useState("");
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [notice, setNotice] = useState("");

  const loadNotifications = useCallback(async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      router.replace("/login");
      return;
    }
    setLoading(true);
    setError("");
    setLoadError("");
    try {
      const [listing, unread] = await Promise.all([
        apiJson<NotificationPage>(
          `/api/v1/notifications?page=${page}&limit=20&unread_only=${unreadOnly}`,
          token,
        ),
        apiJson<UnreadCount>("/api/v1/notifications/unread-count", token),
      ]);
      setItems(listing.items);
      setTotal(listing.total);
      setPages(listing.pages);
      setUnreadCount(unread.count);
    } catch (loadError) {
      const apiError = loadError as ApiError;
      if (apiError.status === 401 || apiError.status === 403) {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
        return;
      }
      setLoadError(apiError.message || "Bildirişləri yükləmək mümkün olmadı.");
    } finally {
      setLoading(false);
    }
  }, [page, unreadOnly, router]);

  useEffect(() => {
    void loadNotifications();
  }, [loadNotifications]);

  const markAsRead = async (item: NotificationItem) => {
    if (item.read_at) return;
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      router.replace("/login");
      return;
    }
    setMarkingId(item.id);
    setError("");
    setNotice("");
    try {
      await apiJson<NotificationItem>(
        `/api/v1/notifications/${item.id}/read`,
        token,
        { method: "PATCH" },
      );
      setNotice("Bildiriş oxunmuş kimi işarələndi.");
      if (unreadOnly && items.length === 1 && page > 1) {
        setPage((current) => Math.max(1, current - 1));
      } else {
        await loadNotifications();
      }
    } catch (markError) {
      const apiError = markError as ApiError;
      if (apiError.status === 401 || apiError.status === 403) {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
        return;
      }
      setError(apiError.message || "Bildirişi yeniləmək mümkün olmadı.");
    } finally {
      setMarkingId("");
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
    <main style={{ maxWidth: 1000, margin: "0 auto", padding: 24 }}>
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
        <h1 style={{ fontSize: 28, fontWeight: 700 }}>Bildirişlər</h1>
        <p style={{ color: "#555", marginTop: 8 }}>
          Şirkətiniz üzrə əməliyyat və təsdiq bildirişləri.
        </p>
        {!loading && !loadError && (
          <p style={{ marginTop: 8, fontWeight: 600 }}>
          Oxunmamış bildiriş: {unreadCount}
          </p>
        )}
      </header>

      {(loadError || error) && (
        <p role="alert" style={{ background: "#fff0f0", color: "#a40000", padding: 12, borderRadius: 6 }}>
          {loadError || error}
        </p>
      )}
      {notice && (
        <p role="status" style={{ background: "#eef8ee", color: "#176b2c", padding: 12, borderRadius: 6 }}>
          {notice}
        </p>
      )}

      <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 18 }}>
        <input
          type="checkbox"
          checked={unreadOnly}
          onChange={(event) => {
            setPage(1);
            setUnreadOnly(event.target.checked);
          }}
        />
        Yalnız oxunmamış bildirişlər
      </label>

      {loading ? (
        <p role="status">Bildirişlər yüklənir...</p>
      ) : loadError ? null : items.length === 0 ? (
        <section style={cardStyle}>
          <p style={{ color: "#555" }}>
            {unreadOnly
              ? "Oxunmamış bildiriş yoxdur."
              : "Hazırda bildiriş yoxdur."}
          </p>
        </section>
      ) : (
        <>
          <p style={{ color: "#555", marginBottom: 12 }}>
            {total} bildiriş · səhifə {page} / {Math.max(1, pages)}
          </p>
          {items.map((item) => (
            <article
              key={item.id}
              style={{
                ...cardStyle,
                borderLeft: item.read_at ? "4px solid #d1d5db" : "4px solid #198754",
                background: item.read_at ? "#fff" : "#f8fff9",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <div style={{ flex: "1 1 420px" }}>
                  <p style={{ fontSize: 12, color: "#555", marginBottom: 6 }}>
                    {eventLabel(item.event_type)} · {formatDate(item.created_at)}
                  </p>
                  <h2 style={{ fontSize: 18, fontWeight: 700 }}>{item.title}</h2>
                  <p style={{ marginTop: 8, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                    {item.body}
                  </p>
                  <p style={{ color: "#666", fontSize: 12, marginTop: 8 }}>
                    {item.read_at ? "Oxunub" : "Oxunmayıb"}
                  </p>
                </div>
                {!item.read_at && (
                  <button
                    type="button"
                    disabled={markingId === item.id}
                    onClick={() => void markAsRead(item)}
                    style={{
                      alignSelf: "center",
                      background: "#198754",
                      color: "#fff",
                      border: 0,
                      borderRadius: 6,
                      padding: "9px 12px",
                      cursor: markingId === item.id ? "wait" : "pointer",
                    }}
                  >
                    {markingId === item.id ? "Yenilənir..." : "Oxunmuş kimi işarələ"}
                  </button>
                )}
              </div>
            </article>
          ))}
          {pages > 1 && (
            <nav aria-label="Bildiriş səhifələnməsi" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginTop: 18 }}>
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                style={{ border: "1px solid #ccc", borderRadius: 6, padding: "8px 12px", background: "#fff", cursor: page <= 1 ? "not-allowed" : "pointer" }}
              >
                Əvvəlki
              </button>
              <span aria-live="polite">Səhifə {page} / {pages}</span>
              <button
                type="button"
                disabled={page >= pages}
                onClick={() => setPage((current) => Math.min(pages, current + 1))}
                style={{ border: "1px solid #ccc", borderRadius: 6, padding: "8px 12px", background: "#fff", cursor: page >= pages ? "not-allowed" : "pointer" }}
              >
                Növbəti
              </button>
            </nav>
          )}
        </>
      )}
    </main>
  );
}
