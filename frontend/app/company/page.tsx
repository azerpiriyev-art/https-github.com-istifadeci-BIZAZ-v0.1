"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = "http://127.0.0.1:8000";
const TOKEN_KEY = "bizaz_token";

type CompanyData = {
  id: string;
  legal_name: string;
  tax_id: string | null;
  legal_form: string;
  vat_registered: boolean;
  vat_rate: number;
  currency: string;
  role: string;
  created_at: string;
  updated_at: string;
};

type CompanyResponse = {
  status: string;
  company: CompanyData;
};

type ErrorResponse = {
  detail?: string;
};

export default function CompanyPage() {
  const router = useRouter();

  const [company, setCompany] = useState<CompanyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [legalName, setLegalName] = useState("");
  const [taxId, setTaxId] = useState("");
  const [legalForm, setLegalForm] = useState("MMC");
  const [vatRegistered, setVatRegistered] = useState(false);
  const [vatRate, setVatRate] = useState("18");

  const loadCompany = async () => {
    const token = localStorage.getItem(TOKEN_KEY);

    if (!token) {
      router.replace("/login");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const res = await fetch(`${API_URL}/api/v1/company/me`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
        cache: "no-store",
      });

      let result: CompanyResponse | ErrorResponse = {};

      try {
        result = await res.json();
      } catch {
        result = {};
      }

      if (res.status === 401 || res.status === 403) {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
        return;
      }

      if (!res.ok) {
        const detail =
          "detail" in result && result.detail
            ? result.detail
            : "Şirkət məlumatlarını almaq mümkün olmadı.";

        setError(detail);
        return;
      }

      if (!("company" in result) || !result.company) {
        setError("Şirkət məlumatı tapılmadı.");
        return;
      }

      setCompany(result.company);
      setLegalName(result.company.legal_name);
      setTaxId(result.company.tax_id || "");
      setLegalForm(result.company.legal_form);
      setVatRegistered(result.company.vat_registered);
      setVatRate(String(result.company.vat_rate));
    } catch (err) {
      console.error("Company loading error:", err);
      setError("Serverlə əlaqə saxlamaq mümkün olmadı.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCompany();
  }, [router]);

  const startEditing = () => {
    if (!company) return;

    setLegalName(company.legal_name);
    setTaxId(company.tax_id || "");
    setLegalForm(company.legal_form);
    setVatRegistered(company.vat_registered);
    setVatRate(String(company.vat_rate));
    setError("");
    setSuccess("");
    setEditing(true);
  };

  const cancelEditing = () => {
    if (!company) return;

    setLegalName(company.legal_name);
    setTaxId(company.tax_id || "");
    setLegalForm(company.legal_form);
    setVatRegistered(company.vat_registered);
    setVatRate(String(company.vat_rate));
    setError("");
    setSuccess("");
    setEditing(false);
  };

  const handleSave = async () => {
    const token = localStorage.getItem(TOKEN_KEY);

    if (!token) {
      router.replace("/login");
      return;
    }

    if (!legalName.trim()) {
      setError("Şirkətin adı boş ola bilməz.");
      return;
    }

    if (taxId && !/^\d{10}$/.test(taxId)) {
      setError("VÖEN 10 rəqəmdən ibarət olmalıdır.");
      return;
    }

    const numericVatRate = Number(vatRate);

    if (
      Number.isNaN(numericVatRate) ||
      numericVatRate < 0 ||
      numericVatRate > 100
    ) {
      setError("ƏDV dərəcəsi 0 ilə 100 arasında olmalıdır.");
      return;
    }

    try {
      setSaving(true);
      setError("");
      setSuccess("");

      const res = await fetch(`${API_URL}/api/v1/company/me`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          legal_name: legalName.trim(),
          ...(taxId ? { tax_id: taxId } : {}),
          legal_form: legalForm,
          vat_registered: vatRegistered,
          vat_rate: numericVatRate,
        }),
      });

      let result: CompanyResponse | ErrorResponse = {};

      try {
        result = await res.json();
      } catch {
        result = {};
      }

      if (res.status === 401 || res.status === 403) {
        localStorage.removeItem(TOKEN_KEY);
        router.replace("/login");
        return;
      }

      if (!res.ok) {
        const detail =
          "detail" in result && result.detail
            ? result.detail
            : "Şirkət məlumatlarını yadda saxlamaq mümkün olmadı.";

        setError(detail);
        return;
      }

      if (!("company" in result) || !result.company) {
        setError("Serverdən düzgün şirkət məlumatı alınmadı.");
        return;
      }

      setCompany(result.company);
      setLegalName(result.company.legal_name);
      setTaxId(result.company.tax_id || "");
      setLegalForm(result.company.legal_form);
      setVatRegistered(result.company.vat_registered);
      setVatRate(String(result.company.vat_rate));

      setEditing(false);
      setSuccess("Şirkət məlumatları uğurla yadda saxlanıldı.");
    } catch (err) {
      console.error("Company update error:", err);
      setError("Serverlə əlaqə saxlamaq mümkün olmadı.");
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(TOKEN_KEY);
    router.replace("/login");
  };

  if (loading) {
    return (
      <main
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <p>Şirkət məlumatları yüklənir...</p>
      </main>
    );
  }

  if (error && !company) {
    return (
      <main
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#f5f7fa",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <div
          style={{
            background: "#ffffff",
            padding: "30px",
            borderRadius: "10px",
            border: "1px solid #ddd",
            textAlign: "center",
          }}
        >
          <h2>BIZAZ</h2>
          <p>{error}</p>

          <button
            onClick={() => loadCompany()}
            style={{
              marginTop: "15px",
              padding: "10px 18px",
              border: "none",
              borderRadius: "6px",
              background: "#198754",
              color: "#ffffff",
              cursor: "pointer",
            }}
          >
            Yenidən yoxla
          </button>
        </div>
      </main>
    );
  }

  if (!company) {
    return null;
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "#f5f7fa",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <header
        style={{
          background: "#ffffff",
          borderBottom: "1px solid #ddd",
          padding: "16px 30px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <strong style={{ fontSize: "22px" }}>BIZAZ</strong>
          <span style={{ marginLeft: "15px", color: "#777" }}>
            Şirkətim
          </span>
        </div>

        <button
          onClick={handleLogout}
          style={{
            padding: "9px 15px",
            background: "#dc3545",
            color: "#fff",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
          }}
        >
          Çıxış
        </button>
      </header>

      <section
        style={{
          maxWidth: "1100px",
          margin: "0 auto",
          padding: "40px 20px",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "10px",
            gap: "15px",
          }}
        >
          <div>
            <h1 style={{ marginBottom: "8px" }}>Şirkətim</h1>
            <p style={{ color: "#666", marginTop: 0 }}>
              Şirkətiniz haqqında əsas məlumatlar.
            </p>
          </div>

          {!editing && (
            <button
              onClick={startEditing}
              style={{
                padding: "10px 18px",
                background: "#0d6efd",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                cursor: "pointer",
                fontWeight: "bold",
              }}
            >
              Redaktə et
            </button>
          )}
        </div>

        {success && (
          <div
            style={{
              background: "#d1e7dd",
              color: "#0f5132",
              border: "1px solid #badbcc",
              padding: "12px 15px",
              borderRadius: "6px",
              marginBottom: "20px",
            }}
          >
            {success}
          </div>
        )}

        {error && (
          <div
            style={{
              background: "#f8d7da",
              color: "#842029",
              border: "1px solid #f5c2c7",
              padding: "12px 15px",
              borderRadius: "6px",
              marginBottom: "20px",
            }}
          >
            {error}
          </div>
        )}

        <div
          style={{
            background: "#ffffff",
            padding: "30px",
            borderRadius: "10px",
            border: "1px solid #ddd",
          }}
        >
          {!editing ? (
            <>
              <h2 style={{ marginTop: 0 }}>{company.legal_name}</h2>

              <p>
                <strong>VÖEN:</strong>{" "}
                {company.tax_id || "Qeyd edilməyib"}
              </p>

              <p>
                <strong>Hüquqi forma:</strong>{" "}
                {company.legal_form}
              </p>

              <p>
                <strong>ƏDV qeydiyyatı:</strong>{" "}
                {company.vat_registered ? "Bəli" : "Xeyr"}
              </p>

              <p>
                <strong>ƏDV dərəcəsi:</strong>{" "}
                {company.vat_rate}%
              </p>

              <p>
                <strong>Valyuta:</strong>{" "}
                {company.currency}
              </p>

              <p>
                <strong>Sizin rolunuz:</strong>{" "}
                {company.role}
              </p>

              <p>
                <strong>Şirkət ID:</strong>{" "}
                {company.id}
              </p>
            </>
          ) : (
            <>
              <h2 style={{ marginTop: 0 }}>Şirkət məlumatlarını redaktə et</h2>

              <div style={{ marginBottom: "20px" }}>
                <label
                  style={{
                    display: "block",
                    marginBottom: "7px",
                    fontWeight: "bold",
                  }}
                >
                  Şirkətin adı
                </label>

                <input
                  type="text"
                  value={legalName}
                  onChange={(e) => setLegalName(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "11px",
                    border: "1px solid #ccc",
                    borderRadius: "6px",
                    boxSizing: "border-box",
                  }}
                />
              </div>

              <div style={{ marginBottom: "20px" }}>
                <label
                  style={{
                    display: "block",
                    marginBottom: "7px",
                    fontWeight: "bold",
                  }}
                >
                  VÖEN
                </label>

                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={10}
                  value={taxId}
                  onChange={(e) =>
                    setTaxId(e.target.value.replace(/\D/g, ""))
                  }
                  placeholder="10 rəqəm"
                  style={{
                    width: "100%",
                    padding: "11px",
                    border: "1px solid #ccc",
                    borderRadius: "6px",
                    boxSizing: "border-box",
                  }}
                />
              </div>

              <div style={{ marginBottom: "20px" }}>
                <label
                  style={{
                    display: "block",
                    marginBottom: "7px",
                    fontWeight: "bold",
                  }}
                >
                  Hüquqi forma
                </label>

                <select
                  value={legalForm}
                  onChange={(e) => setLegalForm(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "11px",
                    border: "1px solid #ccc",
                    borderRadius: "6px",
                    boxSizing: "border-box",
                    background: "#ffffff",
                  }}
                >
                  <option value="MMC">MMC</option>
                  <option value="FERDI_SAHIBKAR">Fərdi sahibkar</option>
                  <option value="ASC">ASC</option>
                  <option value="OTHER">Digər</option>
                </select>
              </div>

              <div style={{ marginBottom: "20px" }}>
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    fontWeight: "bold",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={vatRegistered}
                    onChange={(e) => setVatRegistered(e.target.checked)}
                  />
                  ƏDV qeydiyyatındadır
                </label>
              </div>

              <div style={{ marginBottom: "25px" }}>
                <label
                  style={{
                    display: "block",
                    marginBottom: "7px",
                    fontWeight: "bold",
                  }}
                >
                  ƏDV dərəcəsi (%)
                </label>

                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  value={vatRate}
                  onChange={(e) => setVatRate(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "11px",
                    border: "1px solid #ccc",
                    borderRadius: "6px",
                    boxSizing: "border-box",
                  }}
                />
              </div>

              <div
                style={{
                  display: "flex",
                  gap: "10px",
                  flexWrap: "wrap",
                }}
              >
                <button
                  onClick={handleSave}
                  disabled={saving}
                  style={{
                    padding: "11px 20px",
                    background: saving ? "#6c757d" : "#198754",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    cursor: saving ? "not-allowed" : "pointer",
                    fontWeight: "bold",
                  }}
                >
                  {saving ? "Yadda saxlanılır..." : "Yadda saxla"}
                </button>

                <button
                  onClick={cancelEditing}
                  disabled={saving}
                  style={{
                    padding: "11px 20px",
                    background: "#6c757d",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    cursor: saving ? "not-allowed" : "pointer",
                    fontWeight: "bold",
                  }}
                >
                  Ləğv et
                </button>
              </div>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
