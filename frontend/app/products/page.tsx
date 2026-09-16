"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = "http://127.0.0.1:8000";

type Product = {
  id: string;
  company_id: string;
  name: string;
  sku: string | null;
  category: string | null;
  unit: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type ProductForm = {
  name: string;
  sku: string;
  category: string;
  unit: string;
  description: string;
  is_active: boolean;
};

const emptyForm: ProductForm = {
  name: "",
  sku: "",
  category: "",
  unit: "ədəd",
  description: "",
  is_active: true,
};

export default function ProductsPage() {
  const router = useRouter();

  const [products, setProducts] = useState<Product[]>([]);
  const [form, setForm] = useState<ProductForm>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);

  const [role, setRole] = useState("");
  const [companyName, setCompanyName] = useState("");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const canWrite =
    role === "OWNER" ||
    role === "ADMIN" ||
    role === "PROCUREMENT";

  function getToken(): string | null {
    if (typeof window === "undefined") {
      return null;
    }

    return localStorage.getItem("bizaz_token");
  }

  function handleUnauthorized() {
    localStorage.removeItem("bizaz_token");
    router.push("/login");
  }

  async function apiRequest(
    path: string,
    options: RequestInit = {}
  ): Promise<Response> {
    const token = getToken();

    if (!token) {
      handleUnauthorized();
      throw new Error("AUTH_REQUIRED");
    }

    const headers = new Headers(options.headers);

    headers.set("Authorization", `Bearer ${token}`);
    headers.set("Content-Type", "application/json");

    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      handleUnauthorized();
      throw new Error("UNAUTHORIZED");
    }

    return response;
  }

  async function loadCompany() {
    try {
      const response = await apiRequest("/api/v1/company/me");

      if (!response.ok) {
        return;
      }

      const data = await response.json();

      const company = data.company || data;

      setRole(
        company?.role ||
          data?.role ||
          ""
      );

      setCompanyName(
        company?.name ||
          company?.legal_name ||
          data?.company_name ||
          ""
      );
    } catch (err) {
      if (
        err instanceof Error &&
        (err.message === "AUTH_REQUIRED" ||
          err.message === "UNAUTHORIZED")
      ) {
        return;
      }

      console.error(err);
    }
  }

  async function loadProducts() {
    setLoading(true);
    setError("");

    try {
      const response = await apiRequest("/api/v1/products");

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }

      const data = await response.json();

      if (Array.isArray(data)) {
        setProducts(data);
      } else if (Array.isArray(data.products)) {
        setProducts(data.products);
      } else if (Array.isArray(data.items)) {
        setProducts(data.items);
      } else {
        setProducts([]);
      }
    } catch (err) {
      if (
        err instanceof Error &&
        (err.message === "AUTH_REQUIRED" ||
          err.message === "UNAUTHORIZED")
      ) {
        return;
      }

      setError(
        err instanceof Error
          ? err.message
          : "Məhsullar yüklənərkən xəta baş verdi."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const token = getToken();

    if (!token) {
      router.push("/login");
      return;
    }

    loadCompany();
    loadProducts();
  }, [router]);

  function resetForm() {
    setForm(emptyForm);
    setEditingId(null);
    setError("");
    setSuccess("");
  }

  function startEdit(product: Product) {
    setEditingId(product.id);

    setForm({
      name: product.name || "",
      sku: product.sku || "",
      category: product.category || "",
      unit: product.unit || "ədəd",
      description: product.description || "",
      is_active: product.is_active,
    });

    setError("");
    setSuccess("");

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!canWrite) {
      setError("Sizin məhsul yaratmaq və dəyişmək hüququnuz yoxdur.");
      return;
    }

    if (!form.name.trim()) {
      setError("Məhsul adı daxil edilməlidir.");
      return;
    }

    setSaving(true);
    setError("");
    setSuccess("");

    const payload = {
      name: form.name.trim(),
      sku: form.sku.trim() || null,
      category: form.category.trim() || null,
      unit: form.unit.trim() || "ədəd",
      description: form.description.trim() || null,
      is_active: form.is_active,
    };

    try {
      const path = editingId
        ? `/api/v1/products/${editingId}`
        : "/api/v1/products";

      const method = editingId ? "PUT" : "POST";

      const response = await apiRequest(path, {
        method,
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let message = `HTTP ${response.status}`;

        try {
          const data = await response.json();

          if (typeof data.detail === "string") {
            message = data.detail;
          } else if (Array.isArray(data.detail)) {
            message = data.detail
              .map((item: { msg?: string }) => item.msg || "")
              .filter(Boolean)
              .join(", ");
          }
        } catch {
          // ignore JSON parsing error
        }

        throw new Error(message);
      }

      if (editingId) {
        setSuccess("Məhsul uğurla yeniləndi.");
      } else {
        setSuccess("Məhsul uğurla yaradıldı.");
      }

      resetForm();
      await loadProducts();
    } catch (err) {
      if (
        err instanceof Error &&
        (err.message === "AUTH_REQUIRED" ||
          err.message === "UNAUTHORIZED")
      ) {
        return;
      }

      setError(
        err instanceof Error
          ? err.message
          : "Əməliyyat zamanı xəta baş verdi."
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(product: Product) {
    if (!canWrite) {
      setError("Sizin məhsul silmək hüququnuz yoxdur.");
      return;
    }

    const confirmed = window.confirm(
      `"${product.name}" məhsulunu silmək istədiyinizə əminsiniz?`
    );

    if (!confirmed) {
      return;
    }

    setError("");
    setSuccess("");

    try {
      const response = await apiRequest(
        `/api/v1/products/${product.id}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        let message = `HTTP ${response.status}`;

        try {
          const data = await response.json();

          if (typeof data.detail === "string") {
            message = data.detail;
          }
        } catch {
          // ignore JSON parsing error
        }

        throw new Error(message);
      }

      setSuccess("Məhsul uğurla silindi.");

      if (editingId === product.id) {
        resetForm();
      }

      await loadProducts();
    } catch (err) {
      if (
        err instanceof Error &&
        (err.message === "AUTH_REQUIRED" ||
          err.message === "UNAUTHORIZED")
      ) {
        return;
      }

      setError(
        err instanceof Error
          ? err.message
          : "Məhsul silinərkən xəta baş verdi."
      );
    }
  }

  function formatDate(value: string) {
    if (!value) {
      return "-";
    }

    try {
      return new Date(value).toLocaleString("az-AZ");
    } catch {
      return value;
    }
  }

  return (
    <main style={pageStyle}>
      <div style={containerStyle}>
        <div style={headerStyle}>
          <div>
            <button
              type="button"
              onClick={() => router.push("/dashboard")}
              style={backButtonStyle}
            >
              ← Dashboard
            </button>

            <h1 style={titleStyle}>Məhsullar</h1>

            <p style={subtitleStyle}>
              {companyName
                ? `${companyName} — məhsul kataloqu`
                : "Məhsul kataloqu və idarəetməsi"}
            </p>
          </div>

          <div style={roleBadgeStyle}>
            Rol: {role || "—"}
          </div>
        </div>

        {error && (
          <div style={errorStyle}>
            {error}
          </div>
        )}

        {success && (
          <div style={successStyle}>
            {success}
          </div>
        )}

        {canWrite && (
          <section style={cardStyle}>
            <div style={sectionHeaderStyle}>
              <div>
                <h2 style={sectionTitleStyle}>
                  {editingId
                    ? "Məhsulu redaktə et"
                    : "Yeni məhsul əlavə et"}
                </h2>

                <p style={sectionSubtitleStyle}>
                  Məhsul məlumatlarını daxil edin.
                </p>
              </div>

              {editingId && (
                <button
                  type="button"
                  onClick={resetForm}
                  style={secondaryButtonStyle}
                >
                  Ləğv et
                </button>
              )}
            </div>

            <form onSubmit={handleSubmit}>
              <div style={formGridStyle}>
                <div style={fieldStyle}>
                  <label style={labelStyle}>
                    Məhsul adı *
                  </label>

                  <input
                    value={form.name}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        name: event.target.value,
                      })
                    }
                    placeholder="Məsələn: Təhlükəsizlik dəbilqəsi"
                    style={inputStyle}
                    maxLength={255}
                  />
                </div>

                <div style={fieldStyle}>
                  <label style={labelStyle}>
                    SKU
                  </label>

                  <input
                    value={form.sku}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        sku: event.target.value,
                      })
                    }
                    placeholder="Məsələn: PPE-001"
                    style={inputStyle}
                    maxLength={100}
                  />
                </div>

                <div style={fieldStyle}>
                  <label style={labelStyle}>
                    Kateqoriya
                  </label>

                  <input
                    value={form.category}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        category: event.target.value,
                      })
                    }
                    placeholder="Məsələn: PPE"
                    style={inputStyle}
                    maxLength={255}
                  />
                </div>

                <div style={fieldStyle}>
                  <label style={labelStyle}>
                    Ölçü vahidi *
                  </label>

                  <input
                    value={form.unit}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        unit: event.target.value,
                      })
                    }
                    placeholder="ədəd"
                    style={inputStyle}
                    maxLength={30}
                  />
                </div>

                <div
                  style={{
                    ...fieldStyle,
                    gridColumn: "1 / -1",
                  }}
                >
                  <label style={labelStyle}>
                    Təsvir
                  </label>

                  <textarea
                    value={form.description}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        description: event.target.value,
                      })
                    }
                    placeholder="Məhsul haqqında əlavə məlumat"
                    style={textareaStyle}
                    maxLength={2000}
                    rows={4}
                  />
                </div>

                <div style={checkboxContainerStyle}>
                  <label style={checkboxLabelStyle}>
                    <input
                      type="checkbox"
                      checked={form.is_active}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          is_active: event.target.checked,
                        })
                      }
                    />

                    <span>
                      Aktiv məhsul
                    </span>
                  </label>
                </div>
              </div>

              <div style={formActionsStyle}>
                <button
                  type="submit"
                  disabled={saving}
                  style={{
                    ...primaryButtonStyle,
                    opacity: saving ? 0.6 : 1,
                    cursor: saving
                      ? "not-allowed"
                      : "pointer",
                  }}
                >
                  {saving
                    ? "Saxlanılır..."
                    : editingId
                    ? "Dəyişiklikləri saxla"
                    : "Məhsul yarat"}
                </button>

                {editingId && (
                  <button
                    type="button"
                    onClick={resetForm}
                    style={secondaryButtonStyle}
                  >
                    Təmizlə
                  </button>
                )}
              </div>
            </form>
          </section>
        )}

        {!canWrite && role && (
          <div style={viewerNoticeStyle}>
            <strong>Yalnız oxuma rejimi</strong>
            <span>
              Bu hesabın məhsul yaratmaq, dəyişmək və silmək
              icazəsi yoxdur.
            </span>
          </div>
        )}

        <section style={cardStyle}>
          <div style={sectionHeaderStyle}>
            <div>
              <h2 style={sectionTitleStyle}>
                Məhsul siyahısı
              </h2>

              <p style={sectionSubtitleStyle}>
                Ümumi məhsul sayı: {products.length}
              </p>
            </div>

            <button
              type="button"
              onClick={loadProducts}
              style={secondaryButtonStyle}
              disabled={loading}
            >
              {loading ? "Yüklənir..." : "↻ Yenilə"}
            </button>
          </div>

          {loading ? (
            <div style={emptyStyle}>
              Məhsullar yüklənir...
            </div>
          ) : products.length === 0 ? (
            <div style={emptyStyle}>
              Hələ məhsul yoxdur.
            </div>
          ) : (
            <div style={tableWrapperStyle}>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={thStyle}>Məhsul</th>
                    <th style={thStyle}>SKU</th>
                    <th style={thStyle}>Kateqoriya</th>
                    <th style={thStyle}>Vahid</th>
                    <th style={thStyle}>Status</th>
                    <th style={thStyle}>Yaradılıb</th>

                    {canWrite && (
                      <th style={thStyle}>
                        Əməliyyat
                      </th>
                    )}
                  </tr>
                </thead>

                <tbody>
                  {products.map((product) => (
                    <tr key={product.id}>
                      <td style={tdStyle}>
                        <div style={productNameStyle}>
                          {product.name}
                        </div>

                        {product.description && (
                          <div style={descriptionStyle}>
                            {product.description}
                          </div>
                        )}
                      </td>

                      <td style={tdStyle}>
                        {product.sku || "—"}
                      </td>

                      <td style={tdStyle}>
                        {product.category || "—"}
                      </td>

                      <td style={tdStyle}>
                        {product.unit || "—"}
                      </td>

                      <td style={tdStyle}>
                        <span
                          style={
                            product.is_active
                              ? activeBadgeStyle
                              : inactiveBadgeStyle
                          }
                        >
                          {product.is_active
                            ? "Aktiv"
                            : "Passiv"}
                        </span>
                      </td>

                      <td style={tdStyle}>
                        {formatDate(product.created_at)}
                      </td>

                      {canWrite && (
                        <td style={tdStyle}>
                          <div style={actionStyle}>
                            <button
                              type="button"
                              onClick={() =>
                                startEdit(product)
                              }
                              style={editButtonStyle}
                            >
                              Redaktə
                            </button>

                            <button
                              type="button"
                              onClick={() =>
                                handleDelete(product)
                              }
                              style={deleteButtonStyle}
                            >
                              Sil
                            </button>
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div style={footerStyle}>
          BIZAZ v0.1 • Product Management
        </div>
      </div>
    </main>
  );
}

const pageStyle: React.CSSProperties = {
  minHeight: "100vh",
  background: "#f5f7fa",
  padding: "32px 20px 60px",
  fontFamily:
    "Arial, Helvetica, sans-serif",
  color: "#1f2937",
};

const containerStyle: React.CSSProperties = {
  maxWidth: "1400px",
  margin: "0 auto",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "20px",
  marginBottom: "24px",
};

const backButtonStyle: React.CSSProperties = {
  border: "none",
  background: "transparent",
  padding: "0",
  marginBottom: "10px",
  color: "#2563eb",
  fontSize: "14px",
  cursor: "pointer",
};

const titleStyle: React.CSSProperties = {
  margin: "0",
  fontSize: "32px",
  fontWeight: 700,
};

const subtitleStyle: React.CSSProperties = {
  margin: "8px 0 0",
  color: "#6b7280",
  fontSize: "15px",
};

const roleBadgeStyle: React.CSSProperties = {
  background: "#ffffff",
  border: "1px solid #dbe1e8",
  borderRadius: "999px",
  padding: "9px 14px",
  fontSize: "13px",
  fontWeight: 600,
  whiteSpace: "nowrap",
};

const cardStyle: React.CSSProperties = {
  background: "#ffffff",
  border: "1px solid #e1e5ea",
  borderRadius: "12px",
  padding: "24px",
  marginBottom: "24px",
  boxShadow:
    "0 2px 8px rgba(0, 0, 0, 0.04)",
};

const sectionHeaderStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "16px",
  marginBottom: "20px",
};

const sectionTitleStyle: React.CSSProperties = {
  margin: "0",
  fontSize: "20px",
  fontWeight: 700,
};

const sectionSubtitleStyle: React.CSSProperties = {
  margin: "5px 0 0",
  color: "#6b7280",
  fontSize: "14px",
};

const formGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns:
    "repeat(auto-fit, minmax(260px, 1fr))",
  gap: "18px",
};

const fieldStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "7px",
};

const labelStyle: React.CSSProperties = {
  fontSize: "14px",
  fontWeight: 600,
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "11px 12px",
  border: "1px solid #cfd6df",
  borderRadius: "8px",
  fontSize: "14px",
  outline: "none",
  background: "#ffffff",
};

const textareaStyle: React.CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "11px 12px",
  border: "1px solid #cfd6df",
  borderRadius: "8px",
  fontSize: "14px",
  resize: "vertical",
  fontFamily:
    "Arial, Helvetica, sans-serif",
};

const checkboxContainerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
};

const checkboxLabelStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "9px",
  fontSize: "14px",
  fontWeight: 600,
  cursor: "pointer",
};

const formActionsStyle: React.CSSProperties = {
  display: "flex",
  gap: "10px",
  marginTop: "20px",
};

const primaryButtonStyle: React.CSSProperties = {
  border: "none",
  borderRadius: "8px",
  padding: "11px 18px",
  background: "#2563eb",
  color: "#ffffff",
  fontSize: "14px",
  fontWeight: 600,
};

const secondaryButtonStyle: React.CSSProperties = {
  border: "1px solid #cfd6df",
  borderRadius: "8px",
  padding: "10px 16px",
  background: "#ffffff",
  color: "#374151",
  fontSize: "14px",
  fontWeight: 600,
  cursor: "pointer",
};

const viewerNoticeStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "4px",
  background: "#fff8e1",
  border: "1px solid #f1d27a",
  borderRadius: "10px",
  padding: "14px 16px",
  marginBottom: "24px",
  fontSize: "14px",
};

const errorStyle: React.CSSProperties = {
  background: "#fff1f2",
  border: "1px solid #fecdd3",
  color: "#be123c",
  borderRadius: "10px",
  padding: "13px 16px",
  marginBottom: "18px",
  fontSize: "14px",
};

const successStyle: React.CSSProperties = {
  background: "#ecfdf5",
  border: "1px solid #a7f3d0",
  color: "#047857",
  borderRadius: "10px",
  padding: "13px 16px",
  marginBottom: "18px",
  fontSize: "14px",
};

const tableWrapperStyle: React.CSSProperties = {
  overflowX: "auto",
  border: "1px solid #e5e7eb",
  borderRadius: "9px",
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  minWidth: "950px",
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "13px 14px",
  background: "#f8fafc",
  borderBottom: "1px solid #dfe4ea",
  fontSize: "13px",
  fontWeight: 700,
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "14px",
  borderBottom: "1px solid #eee",
  fontSize: "14px",
  verticalAlign: "top",
};

const productNameStyle: React.CSSProperties = {
  fontWeight: 600,
  color: "#111827",
};

const descriptionStyle: React.CSSProperties = {
  marginTop: "5px",
  color: "#6b7280",
  fontSize: "12px",
  maxWidth: "350px",
  lineHeight: 1.4,
};

const activeBadgeStyle: React.CSSProperties = {
  display: "inline-block",
  padding: "5px 9px",
  borderRadius: "999px",
  background: "#dcfce7",
  color: "#166534",
  fontSize: "12px",
  fontWeight: 700,
};

const inactiveBadgeStyle: React.CSSProperties = {
  display: "inline-block",
  padding: "5px 9px",
  borderRadius: "999px",
  background: "#f3f4f6",
  color: "#4b5563",
  fontSize: "12px",
  fontWeight: 700,
};

const actionStyle: React.CSSProperties = {
  display: "flex",
  gap: "7px",
};

const editButtonStyle: React.CSSProperties = {
  border: "1px solid #bfdbfe",
  borderRadius: "7px",
  padding: "7px 10px",
  background: "#eff6ff",
  color: "#1d4ed8",
  fontSize: "12px",
  fontWeight: 600,
  cursor: "pointer",
};

const deleteButtonStyle: React.CSSProperties = {
  border: "1px solid #fecaca",
  borderRadius: "7px",
  padding: "7px 10px",
  background: "#fef2f2",
  color: "#b91c1c",
  fontSize: "12px",
  fontWeight: 600,
  cursor: "pointer",
};

const emptyStyle: React.CSSProperties = {
  padding: "50px 20px",
  textAlign: "center",
  color: "#6b7280",
  fontSize: "14px",
};

const footerStyle: React.CSSProperties = {
  textAlign: "center",
  color: "#9ca3af",
  fontSize: "12px",
  paddingTop: "10px",
};
