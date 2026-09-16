"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = "http://127.0.0.1:8000";

export default function LoginPage() {
  const router = useRouter();

  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });

  const [loading, setLoading] = useState(false);
  const [responseMsg, setResponseMsg] = useState("");

  const handleLogin = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    setLoading(true);
    setResponseMsg("");

    try {
      const res = await fetch(`${API_URL}/api/v1/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      });

      const data = await res.json();

      if (!res.ok) {
        const detail =
          typeof data.detail === "string"
            ? data.detail
            : "E-poçt və ya şifrə yanlışdır.";

        setResponseMsg(`Login xətası (${res.status}): ${detail}`);
        return;
      }

      if (!data.token) {
        setResponseMsg("Login uğurludur, lakin token cavabda yoxdur.");
        return;
      }

      localStorage.setItem("bizaz_token", data.token);

      setResponseMsg("Uğurla daxil oldunuz! Dashboard açılır...");

      setTimeout(() => {
        router.push("/dashboard");
      }, 500);
    } catch (error) {
      console.error(error);
      setResponseMsg(
        "Serverlə əlaqə saxlamaq mümkün olmadı. Backend-in işlədiyini yoxlayın."
      );
    } finally {
      setLoading(false);
    }
  };

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
          width: "100%",
          maxWidth: "420px",
          background: "#ffffff",
          padding: "32px",
          borderRadius: "12px",
          boxShadow: "0 4px 20px rgba(0,0,0,0.08)",
        }}
      >
        <h1 style={{ marginBottom: "8px", fontSize: "28px" }}>
          BIZAZ
        </h1>

        <p style={{ marginBottom: "25px", color: "#666" }}>
          Biznes platformasına giriş
        </p>

        <form
          onSubmit={handleLogin}
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "18px",
          }}
        >
          <div>
            <label
              style={{
                display: "block",
                marginBottom: "7px",
                fontWeight: "600",
              }}
            >
              E-poçt
            </label>

            <input
              type="email"
              required
              autoComplete="email"
              value={formData.email}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  email: e.target.value,
                })
              }
              placeholder="example@bizaz.az"
              style={{
                width: "100%",
                padding: "12px",
                border: "1px solid #ccc",
                borderRadius: "6px",
                boxSizing: "border-box",
                fontSize: "15px",
              }}
            />
          </div>

          <div>
            <label
              style={{
                display: "block",
                marginBottom: "7px",
                fontWeight: "600",
              }}
            >
              Şifrə
            </label>

            <input
              type="password"
              required
              autoComplete="current-password"
              value={formData.password}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  password: e.target.value,
                })
              }
              placeholder="Şifrənizi daxil edin"
              style={{
                width: "100%",
                padding: "12px",
                border: "1px solid #ccc",
                borderRadius: "6px",
                boxSizing: "border-box",
                fontSize: "15px",
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: "12px",
              background: loading ? "#999" : "#198754",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              cursor: loading ? "not-allowed" : "pointer",
              fontSize: "16px",
              fontWeight: "600",
            }}
          >
            {loading ? "Yoxlanılır..." : "Daxil ol"}
          </button>
        </form>

        {responseMsg && (
          <div
            style={{
              marginTop: "20px",
              padding: "12px",
              background: "#f1f3f5",
              borderRadius: "6px",
              color: "#333",
            }}
          >
            {responseMsg}
          </div>
        )}
      </div>
    </main>
  );
}
