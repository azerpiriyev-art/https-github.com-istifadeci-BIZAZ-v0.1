"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = "http://127.0.0.1:8000";
const TOKEN_KEY = "bizaz_token";

type UserData = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
};

type CompanyData = {
  id: string;
  name: string;
  role: string;
};

type MeResponse = {
  status: string;
  user: UserData;
  company: CompanyData | null;
};

export default function DashboardPage() {
  const router = useRouter();

  const [data, setData] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    const loadCurrentUser = async () => {
      const token = localStorage.getItem(TOKEN_KEY);

      // Token yoxdur
      if (!token) {
        router.replace("/login");
        return;
      }

      try {
        const res = await fetch(`${API_URL}/api/v1/me`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/json",
          },
          signal: controller.signal,
          cache: "no-store",
        });

        let result: MeResponse | { detail?: string };

        try {
          result = await res.json();
        } catch {
          result = {};
        }

        // Token etibarsızdır və ya istifadəçi aktiv deyil
        if (res.status === 401 || res.status === 403) {
          localStorage.removeItem(TOKEN_KEY);
          router.replace("/login");
          return;
        }

        // Digər server xətaları
        if (!res.ok) {
          const detail =
            "detail" in result && result.detail
              ? result.detail
              : "İstifadəçi məlumatlarını almaq mümkün olmadı.";

          setError(detail);
          return;
        }

        // Cavabın gözlənilən struktura uyğunluğu
        if (
          !("user" in result) ||
          !result.user ||
          !result.user.is_active
        ) {
          localStorage.removeItem(TOKEN_KEY);
          router.replace("/login");
          return;
        }

        setData(result as MeResponse);
      } catch (err) {
        // Component artıq aktiv deyilsə, xəta göstərmə
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }

        console.error("Dashboard auth error:", err);

        setError(
          "Serverlə əlaqə saxlamaq mümkün olmadı."
        );
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    loadCurrentUser();

    return () => {
      controller.abort();
    };
  }, [router]);

  const handleLogout = () => {
    // Lokal sessiyanı dərhal bağla
    localStorage.removeItem(TOKEN_KEY);

    // Login səhifəsinə qayıt
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
        <p>Dashboard yüklənir...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "Arial, sans-serif",
          background: "#f5f7fa",
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
            onClick={() => window.location.reload()}
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

          <button
            onClick={handleLogout}
            style={{
              marginTop: "15px",
              marginLeft: "10px",
              padding: "10px 18px",
              border: "none",
              borderRadius: "6px",
              background: "#dc3545",
              color: "#ffffff",
              cursor: "pointer",
            }}
          >
            Giriş səhifəsi
          </button>
        </div>
      </main>
    );
  }

  if (!data) {
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
          <strong
            style={{
              fontSize: "22px",
            }}
          >
            BIZAZ
          </strong>

          <span
            style={{
              marginLeft: "15px",
              color: "#777",
            }}
          >
            İdarəetmə Paneli
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
        <h1>
          Salam, {data.user.full_name}!
        </h1>

        <p
          style={{
            color: "#666",
            marginBottom: "30px",
          }}
        >
          BIZAZ platformasına uğurla daxil olmusunuz.
        </p>

        <div
          style={{
            display: "grid",
            gridTemplateColumns:
              "repeat(auto-fit, minmax(280px, 1fr))",
            gap: "20px",
          }}
        >
          <div
            style={{
              background: "#ffffff",
              padding: "25px",
              borderRadius: "10px",
              border: "1px solid #ddd",
            }}
          >
            <h3>İstifadəçi</h3>

            <p>
              <strong>Ad:</strong>{" "}
              {data.user.full_name}
            </p>

            <p>
              <strong>E-poçt:</strong>{" "}
              {data.user.email}
            </p>

            <p>
              <strong>Status:</strong>{" "}
              {data.user.is_active
                ? "Aktiv"
                : "Deaktiv"}
            </p>
          </div>

          <div
            style={{
              background: "#ffffff",
              padding: "25px",
              borderRadius: "10px",
              border: "1px solid #ddd",
            }}
          >
            <h3>Şirkət</h3>

            {data.company ? (
              <>
                <p>
                  <strong>Şirkət:</strong>{" "}
                  {data.company.name}
                </p>

                <p>
                  <strong>Rol:</strong>{" "}
                  {data.company.role}
                </p>

                <p>
                  <strong>Şirkət ID:</strong>{" "}
                  {data.company.id}
                </p>
              </>
            ) : (
              <p>
                Şirkət məlumatı tapılmadı.
              </p>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}