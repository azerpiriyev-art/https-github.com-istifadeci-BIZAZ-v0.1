'use client';

import { FormEvent, useEffect, useState } from 'react';

const API_URL = 'http://127.0.0.1:8000';

type Product = {
  id: string;
  name: string;
  sku: string;
  unit: string;
  is_active: boolean;
};

type RequestItem = {
  product_id: string;
  quantity: string;
  unit: string;
  required_date: string;
  specifications: string;
  notes: string;
};

const emptyItem = (): RequestItem => ({
  product_id: '',
  quantity: '',
  unit: '',
  required_date: '',
  specifications: '',
  notes: '',
});

export default function PurchaseRequestsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [requestNumber, setRequestNumber] = useState('');
  const [requestDate, setRequestDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<RequestItem[]>([emptyItem()]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    void loadProducts();
  }, []);

  async function loadProducts() {
    try {
      const token = localStorage.getItem('bizaz_token');
      if (!token) throw new Error('Sistemə daxil olmaq tələb olunur.');

      const response = await fetch(`${API_URL}/api/v1/products`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Məhsullar yüklənmədi.');
      }

      setProducts((data.products || []).filter((p: Product) => p.is_active));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Məhsullar yüklənmədi.');
    }
  }

  function updateItem(index: number, field: keyof RequestItem, value: string) {
    setItems((current) =>
      current.map((item, i) => (i === index ? { ...item, [field]: value } : item))
    );
  }

  function selectProduct(index: number, productId: string) {
    const product = products.find((p) => p.id === productId);
    setItems((current) =>
      current.map((item, i) =>
        i === index ? { ...item, product_id: productId, unit: product?.unit || '' } : item
      )
    );
  }

  function addItem() {
    setItems((current) => [...current, emptyItem()]);
  }

  function removeItem(index: number) {
    setItems((current) => (current.length === 1 ? current : current.filter((_, i) => i !== index)));
  }

  async function saveRequest(status: 'DRAFT' | 'SUBMITTED') {
    setMessage('');
    setError('');

    if (!requestNumber.trim()) {
      setError('Sorğu nömrəsi daxil edilməlidir.');
      return;
    }

    if (items.some((item) => !item.product_id)) {
      setError('Bütün sətirlərdə məhsul seçilməlidir.');
      return;
    }

    if (items.some((item) => !item.quantity || Number(item.quantity) <= 0)) {
      setError('Miqdar 0-dan böyük olmalıdır.');
      return;
    }

    try {
      setSaving(true);
      const token = localStorage.getItem('bizaz_token');
      if (!token) throw new Error('Sistemə daxil olmaq tələb olunur.');

      const payload = {
        request_number: requestNumber.trim(),
        request_date: requestDate || null,
        status,
        notes: notes.trim() || null,
        items: items.map((item) => ({
          product_id: item.product_id,
          quantity: Number(item.quantity),
          unit: item.unit,
          required_date: item.required_date || null,
          specifications: item.specifications.trim() || null,
          notes: item.notes.trim() || null,
        })),
      };

      const response = await fetch(`${API_URL}/api/v1/procurement/purchase-requests`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail ? JSON.stringify(data.detail) : 'Satınalma sorğusu yaradılmadı.');
      }

      setMessage(`Satınalma sorğusu yaradıldı — ${status === 'DRAFT' ? 'Qaralama' : 'Təqdim edilmiş'}.`);
      setRequestNumber('');
      setNotes('');
      setItems([emptyItem()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Satınalma sorğusu yaradılmadı.');
    } finally {
      setSaving(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void saveRequest('SUBMITTED');
  }

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <div style={styles.header}>
          <div>
            <div style={styles.eyebrow}>BIZAZ • PROCUREMENT</div>
            <h1 style={styles.title}>Satınalma sorğusu</h1>
            <p style={styles.subtitle}>
              Təchizatçılardan təklif toplamaq üçün yeni satınalma sorğusu yaradın.
            </p>
          </div>
        </div>

        <div style={styles.steps}>
          <span style={styles.stepActive}>1. Sorğu</span>
          <span>→</span>
          <span>2. Təkliflər</span>
          <span>→</span>
          <span>3. Müqayisə</span>
          <span>→</span>
          <span>4. Seçim</span>
          <span>→</span>
          <span>5. Sifariş</span>
        </div>

        {message && <div style={styles.success}>{message}</div>}
        {error && <div style={styles.error}>{error}</div>}

        <form onSubmit={submit}>
          <section style={styles.card}>
            <h2 style={styles.sectionTitle}>Sorğu məlumatları</h2>
            <div style={styles.grid3}>
              <label style={styles.label}>
                Sorğu nömrəsi *
                <input
                  value={requestNumber}
                  onChange={(e) => setRequestNumber(e.target.value)}
                  placeholder="PR-2026-001"
                  style={styles.input}
                />
              </label>

              <label style={styles.label}>
                Sorğu tarixi
                <input
                  type="date"
                  value={requestDate}
                  onChange={(e) => setRequestDate(e.target.value)}
                  style={styles.input}
                />
              </label>

              <label style={styles.label}>
                Status
                <input value="Qaralama / Təqdim" readOnly style={{ ...styles.input, background: '#f9fafb' }} />
              </label>
            </div>

            <label style={{ ...styles.label, marginTop: 18 }}>
              Ümumi qeyd
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder="Sorğu üzrə ümumi məlumat..."
                style={styles.textarea}
              />
            </label>
          </section>

          <section style={styles.card}>
            <div style={styles.sectionHeader}>
              <h2 style={styles.sectionTitle}>Sorğu məhsulları</h2>
              <button type="button" onClick={addItem} style={styles.secondaryButton}>
                + Məhsul əlavə et
              </button>
            </div>

            {items.map((item, index) => (
              <div key={index} style={styles.itemCard}>
                <div style={styles.itemNumber}>Məhsul sətri {index + 1}</div>

                <div style={styles.grid4}>
                  <label style={styles.label}>
                    Məhsul *
                    <select
                      value={item.product_id}
                      onChange={(e) => selectProduct(index, e.target.value)}
                      style={styles.input}
                    >
                      <option value="">Məhsul seçin</option>
                      {products.map((product) => (
                        <option key={product.id} value={product.id}>
                          {product.name} — {product.sku}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label style={styles.label}>
                    Miqdar *
                    <input
                      type="number"
                      min="0.0001"
                      step="any"
                      value={item.quantity}
                      onChange={(e) => updateItem(index, 'quantity', e.target.value)}
                      placeholder="100"
                      style={styles.input}
                    />
                  </label>

                  <label style={styles.label}>
                    Ölçü vahidi
                    <input value={item.unit} readOnly placeholder="Avtomatik" style={{ ...styles.input, background: '#f9fafb' }} />
                  </label>

                  <label style={styles.label}>
                    Tələb olunan tarix
                    <input
                      type="date"
                      value={item.required_date}
                      onChange={(e) => updateItem(index, 'required_date', e.target.value)}
                      style={styles.input}
                    />
                  </label>
                </div>

                <div style={styles.grid2}>
                  <label style={styles.label}>
                    Texniki spesifikasiya
                    <textarea
                      value={item.specifications}
                      onChange={(e) => updateItem(index, 'specifications', e.target.value)}
                      rows={3}
                      style={styles.textarea}
                      placeholder="Texniki tələblər..."
                    />
                  </label>

                  <label style={styles.label}>
                    Sətir qeydi
                    <textarea
                      value={item.notes}
                      onChange={(e) => updateItem(index, 'notes', e.target.value)}
                      rows={3}
                      style={styles.textarea}
                      placeholder="Əlavə qeyd..."
                    />
                  </label>
                </div>

                {items.length > 1 && (
                  <button type="button" onClick={() => removeItem(index)} style={styles.deleteButton}>
                    Bu sətri sil
                  </button>
                )}
              </div>
            ))}
          </section>

          <div style={styles.actions}>
            <button
              type="button"
              disabled={saving}
              onClick={() => void saveRequest('DRAFT')}
              style={styles.secondaryButton}
            >
              Qaralama saxla
            </button>

            <button type="submit" disabled={saving} style={styles.primaryButton}>
              {saving ? 'Göndərilir...' : 'Təqdim et'}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: '100vh', background: '#f5f7fb', padding: 32, color: '#172033' },
  container: { maxWidth: 1400, margin: '0 auto' },
  header: { marginBottom: 20 },
  eyebrow: { fontSize: 12, fontWeight: 700, letterSpacing: 1, color: '#667085', marginBottom: 6 },
  title: { margin: 0, fontSize: 30 },
  subtitle: { margin: '8px 0 0', color: '#667085' },
  steps: { display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', padding: '14px 18px', background: '#fff', border: '1px solid #e4e7ec', borderRadius: 10, marginBottom: 20, color: '#667085', fontSize: 14 },
  stepActive: { color: '#175cd3', fontWeight: 700 },
  success: { padding: 14, marginBottom: 18, background: '#ecfdf3', border: '1px solid #abefc6', borderRadius: 8, color: '#067647' },
  error: { padding: 14, marginBottom: 18, background: '#fef3f2', border: '1px solid #fecdca', borderRadius: 8, color: '#b42318' },
  card: { background: '#fff', border: '1px solid #e4e7ec', borderRadius: 12, padding: 24, marginBottom: 20 },
  sectionHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, marginBottom: 18 },
  sectionTitle: { margin: 0, fontSize: 20 },
  grid3: { display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 18 },
  grid4: { display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1.2fr', gap: 14 },
  grid2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 14 },
  label: { display: 'flex', flexDirection: 'column', gap: 6, fontWeight: 600, fontSize: 14 },
  input: { width: '100%', boxSizing: 'border-box', padding: '10px 12px', border: '1px solid #d0d5dd', borderRadius: 8, fontSize: 14, background: '#fff', color: '#172033' },
  textarea: { width: '100%', boxSizing: 'border-box', padding: '10px 12px', border: '1px solid #d0d5dd', borderRadius: 8, fontSize: 14, resize: 'vertical', fontFamily: 'inherit' },
  itemCard: { border: '1px solid #eaecf0', borderRadius: 10, padding: 18, marginBottom: 14 },
  itemNumber: { fontSize: 13, color: '#667085', fontWeight: 700, marginBottom: 14 },
  actions: { display: 'flex', justifyContent: 'flex-end', gap: 12 },
  primaryButton: { border: 0, borderRadius: 8, padding: '11px 18px', background: '#175cd3', color: '#fff', fontWeight: 600, cursor: 'pointer' },
  secondaryButton: { border: '1px solid #d0d5dd', borderRadius: 8, padding: '10px 16px', background: '#fff', color: '#344054', fontWeight: 600, cursor: 'pointer' },
  deleteButton: { marginTop: 12, border: 0, background: 'transparent', color: '#b42318', cursor: 'pointer', fontWeight: 600, padding: 0 },
};
