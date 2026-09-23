'use client';

import { CSSProperties, useEffect, useState } from 'react';

const API_URL = 'http://127.0.0.1:8001';

type Offer = {
  offer_id: string;
  offer_number: string;
  offer_date: string | null;
  valid_until: string | null;
  supplier_id: string;
  supplier_name: string;
  quantity: number | string;
  unit: string;
  unit_price: number | string;
  vat_rate: number | string;
  vat_amount: number | string;
  line_total: number | string;
  delivery_days: number | null;
  rank: number;
};

type ComparisonItem = {
  request_item_id: string;
  product_id: string;
  product_name: string;
  requested_quantity: number | string;
  unit: string;
  offers: Offer[];
};


type ActiveSelection = {
  id: string;
  supplier_offer_id: string;
  status: string;
  purchase_order_id: string | null;
};
type ComparisonResponse = {
  purchase_request_id: string;
  request_number: string;
  request_date: string | null;
  status: string;
  active_selection: ActiveSelection | null;
  items: ComparisonItem[];
};

export default function ComparisonPage() {
  const [requestId, setRequestId] = useState('');
  const [data, setData] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [selectedOfferId, setSelectedOfferId] = useState('');
  const [justification, setJustification] = useState('');
  const [selecting, setSelecting] = useState(false);
  const [selectionMessage, setSelectionMessage] = useState('');
  const [selectionError, setSelectionError] = useState('');
  const [selectionId, setSelectionId] = useState('');
  const [orderNumber, setOrderNumber] = useState('');
  const [orderNotes, setOrderNotes] = useState('');
  const [creatingPO, setCreatingPO] = useState(false);
  const [poMessage, setPoMessage] = useState('');
  const [poError, setPoError] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('requestId') || '';
    setRequestId(id);

    if (id) {
      void loadComparison(id);
    } else {
      setLoading(false);
      setError('Satınalma sorğusu seçilməyib.');
    }
  }, []);

  async function loadComparison(id: string) {
    setLoading(true);
    setError('');
    setSelectionError('');

    try {
      const token = localStorage.getItem('bizaz_token');

      if (!token) {
        throw new Error('Sistemə daxil olmaq tələb olunur.');
      }

      const response = await fetch(
        `${API_URL}/api/v1/procurement/purchase-requests/${id}/comparison`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof result.detail === 'string'
            ? result.detail
            : 'Müqayisə məlumatları yüklənmədi.'
        );
      }

      setData(result);
      setSelectionId(result.active_selection?.id || '');
      setSelectedOfferId(result.active_selection?.supplier_offer_id || '');
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Müqayisə məlumatları yüklənmədi.'
      );
    } finally {
      setLoading(false);
    }
  }

  async function selectSupplierOffer() {
    setSelectionMessage('');
    setSelectionError('');

    if (!requestId) {
      setSelectionError('Satınalma sorğusu müəyyən edilməyib.');
      return;
    }

    if (!selectedOfferId) {
      setSelectionError('Təchizatçı təklifi seçilməlidir.');
      return;
    }

    if (!justification.trim()) {
      setSelectionError('Seçim üçün əsaslandırma daxil edilməlidir.');
      return;
    }

    setSelecting(true);

    try {
      const token = localStorage.getItem('bizaz_token');

      if (!token) {
        throw new Error('Sistemə daxil olmaq tələb olunur.');
      }

      const response = await fetch(
        `${API_URL}/api/v1/procurement/offer-selections`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            purchase_request_id: requestId,
            supplier_offer_id: selectedOfferId,
            justification: justification.trim(),
          }),
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof result.detail === 'string'
            ? result.detail
            : 'Təchizatçı seçimi təsdiqlənmədi.'
        );
      }

      setSelectionMessage(
        `Təchizatçı seçimi təsdiqləndi. Seçim ID: ${result.id}`
      );
    } catch (e) {
      setSelectionError(
        e instanceof Error
          ? e.message
          : 'Təchizatçı seçimi təsdiqlənmədi.'
      );
    } finally {
      setSelecting(false);
    }
  }

  async function createPurchaseOrder() {
    setPoMessage('');
    setPoError('');

    if (!selectionId) {
      setPoError('Əvvəlcə təchizatçı seçimi təsdiqlənməlidir.');
      return;
    }

    if (!orderNumber.trim()) {
      setPoError('Satınalma sifarişi nömrəsi daxil edilməlidir.');
      return;
    }

    setCreatingPO(true);

    try {
      const token = localStorage.getItem('bizaz_token');

      if (!token) {
        throw new Error('Sistemə daxil olmaq tələb olunur.');
      }

      const response = await fetch(
        `${API_URL}/api/v1/procurement/offer-selections/${selectionId}/purchase-order`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            order_number: orderNumber.trim(),
            order_date: null,
            notes: orderNotes.trim() || null,
          }),
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof result.detail === 'string'
            ? result.detail
            : 'Satınalma sifarişi yaradılmadı.'
        );
      }

      setPoMessage(
        `Satınalma sifarişi yaradıldı — ${result.order_number}. ` +
        `Status: ${result.status}. ` +
        `Cəmi: ${Number(result.total_amount).toFixed(2)} ${result.currency}. ` +
        `PO ID: ${result.purchase_order_id}`
      );
    } catch (e) {
      setPoError(
        e instanceof Error
          ? e.message
          : 'Satınalma sifarişi yaradılmadı.'
      );
    } finally {
      setCreatingPO(false);
    }
  }
  if (loading) {
    return (
      <main style={styles.page}>
        <div style={styles.container}>
          <div style={styles.card}>Müqayisə məlumatları yüklənir...</div>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main style={styles.page}>
        <div style={styles.container}>
          <div style={styles.error}>{error}</div>
        </div>
      </main>
    );
  }

  if (!data) {
    return null;
  }

  const totalOffers = data.items.reduce(
    (sum, item) => sum + item.offers.length,
    0
  );

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <div style={styles.eyebrow}>BIZAZ • PROCUREMENT</div>

        <h1 style={styles.title}>Təkliflərin müqayisəsi</h1>

        <p style={styles.subtitle}>
          Təqdim edilmiş təchizatçı təkliflərinin qiymət, ƏDV və çatdırılma
          müddəti üzrə müqayisəsi.
        </p>

        <div style={styles.workflow}>
          <span>Sorğu</span>
          <span>→</span>
          <span>Təkliflər</span>
          <span>→</span>
          <strong>3. Müqayisə</strong>
          <span>→</span>
          <strong>4. Seçim</strong>
          <span>→</span>
          <span>5. Sifariş</span>
        </div>

        <section style={styles.card}>
          <div style={styles.cardHeader}>
            <div>
              <div style={styles.sectionTitle}>Satınalma sorğusu</div>

              <div style={styles.meta}>
                <span>{data.request_number}</span>
                <span>
                  Tarix:{' '}
                  {data.request_date
                    ? new Date(data.request_date).toLocaleDateString('az-AZ')
                    : '—'}
                </span>
                <span>Status: {data.status}</span>
              </div>
            </div>

            <button
              type="button"
              onClick={() => void loadComparison(requestId)}
              style={styles.secondaryButton}
            >
              Yenilə
            </button>
          </div>
        </section>

        {data.items.map((item) => (
          <section key={item.request_item_id} style={styles.card}>
            <h2 style={styles.productTitle}>{item.product_name}</h2>

            <div style={styles.smallText}>
              Tələb olunan miqdar:{' '}
              <strong>
                {Number(item.requested_quantity).toFixed(2)}
              </strong>{' '}
              {item.unit}
            </div>

            {item.offers.length === 0 ? (
              <div style={styles.emptyState}>
                Bu məhsul üzrə qüvvədə olan təqdim edilmiş təklif yoxdur.
              </div>
            ) : (
              <div style={styles.tableWrap}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Seç</th>
                      <th style={styles.th}>Sıra</th>
                      <th style={styles.th}>Təchizatçı</th>
                      <th style={styles.th}>Təklif №</th>
                      <th style={styles.th}>Miqdar</th>
                      <th style={styles.th}>Vahid qiymət</th>
                      <th style={styles.th}>ƏDV</th>
                      <th style={styles.th}>Cəmi</th>
                      <th style={styles.th}>Çatdırılma</th>
                      <th style={styles.th}>Qüvvədədir</th>
                    </tr>
                  </thead>

                  <tbody>
                    {item.offers.map((offer) => (
                      <tr key={offer.offer_id}>
                        <td style={styles.td}>
                          <input
                            type="radio"
                            name="supplier-offer-selection"
                            checked={selectedOfferId === offer.offer_id}
                            onChange={() =>
                              setSelectedOfferId(offer.offer_id)
                            }
                          />
                        </td>

                        <td style={styles.td}>
                          <span
                            style={
                              offer.rank === 1
                                ? styles.rankBadge
                                : styles.rankBadgeNormal
                            }
                          >
                            {offer.rank}
                          </span>
                        </td>

                        <td style={styles.td}>
                          <strong>{offer.supplier_name}</strong>
                        </td>

                        <td style={styles.td}>{offer.offer_number}</td>

                        <td style={styles.td}>
                          {Number(offer.quantity).toFixed(2)} {offer.unit}
                        </td>

                        <td style={styles.td}>
                          {Number(offer.unit_price).toFixed(2)} AZN
                        </td>

                        <td style={styles.td}>
                          {Number(offer.vat_amount).toFixed(2)} AZN
                          <div style={styles.smallText}>
                            {Number(offer.vat_rate).toFixed(2)}%
                          </div>
                        </td>

                        <td style={styles.td}>
                          <strong>
                            {Number(offer.line_total).toFixed(2)} AZN
                          </strong>
                        </td>

                        <td style={styles.td}>
                          {offer.delivery_days === null
                            ? '—'
                            : `${offer.delivery_days} gün`}
                        </td>

                        <td style={styles.td}>
                          {offer.valid_until
                            ? new Date(
                                offer.valid_until
                              ).toLocaleDateString('az-AZ')
                            : 'Məhdudiyyətsiz'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        ))}

        {totalOffers > 0 && (
          <section style={styles.selectionCard}>
            <div style={styles.sectionTitle}>
              4. Təchizatçı seçimi
            </div>

            <p style={styles.selectionHint}>
              Müqayisə cədvəlindən bir təchizatçı təklifi seçin və seçiminizi
              əsaslandırın.
            </p>

            {selectedOfferId && (
              <div style={styles.selectedInfo}>
                Seçilmiş təklif:{' '}
                <strong>
                  {data.items
                    .flatMap((item) => item.offers)
                    .find((offer) => offer.offer_id === selectedOfferId)
                    ?.offer_number || selectedOfferId}
                </strong>
              </div>
            )}

            <label style={styles.label}>
              Seçim üçün əsaslandırma
            </label>

            <textarea
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
              placeholder="Məsələn: ən aşağı ümumi qiymət və 5 gün çatdırılma müddəti."
              rows={4}
              style={styles.textarea}
              maxLength={5000}
            />

            {selectionMessage && (
              <div style={styles.success}>{selectionMessage}</div>
            )}

            {selectionError && (
              <div style={styles.error}>{selectionError}</div>
            )}

            <div style={styles.actions}>
              <button
                type="button"
                onClick={() => void selectSupplierOffer()}
                disabled={selecting || !selectedOfferId}
                style={styles.primaryButton}
              >
                {selecting
                  ? 'Seçim təsdiqlənir...'
                  : 'Təchizatçını seç və təsdiqlə'}
              </button>
            </div>
          </section>
        )}

        {selectionId && (
          <section style={styles.poCard}>
            <div style={styles.sectionTitle}>
              5. Satınalma sifarişinin yaradılması
            </div>

            <p style={styles.selectionHint}>
              Təchizatçı seçimi təsdiqləndi. İndi həmin seçim əsasında
              Satınalma Sifarişi (PO) yarada bilərsiniz.
            </p>

            <label style={styles.label}>
              Sifariş nömrəsi
            </label>

            <input
              value={orderNumber}
              onChange={(e) => setOrderNumber(e.target.value)}
              placeholder="Məsələn: PO-UI-2026-001"
              style={styles.input}
              maxLength={50}
            />

            <label style={styles.label}>
              Qeyd
            </label>

            <textarea
              value={orderNotes}
              onChange={(e) => setOrderNotes(e.target.value)}
              placeholder="Satınalma sifarişi üzrə əlavə qeyd..."
              rows={3}
              style={styles.textarea}
              maxLength={5000}
            />

            {poMessage && (
              <div style={styles.success}>{poMessage}</div>
            )}

            {poError && (
              <div style={styles.error}>{poError}</div>
            )}

            <div style={styles.actions}>
              <button
                type="button"
                onClick={() => void createPurchaseOrder()}
                disabled={creatingPO}
                style={styles.primaryButton}
              >
                {creatingPO
                  ? 'Satınalma sifarişi yaradılır...'
                  : 'Satınalma sifarişini yarat'}
              </button>
            </div>
          </section>
        )}

        <div style={styles.actions}>
          <button
            type="button"
            onClick={() =>
              (window.location.href =
                '/procurement/purchase-requests')
            }
            style={styles.secondaryButton}
          >
            ← Satınalma sorğularına qayıt
          </button>
        </div>
      </div>
    </main>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: '100vh',
    background: '#f5f7fa',
    padding: '28px 20px 60px',
    color: '#101828',
  },
  container: {
    maxWidth: 1080,
    margin: '0 auto',
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 1.2,
    color: '#667085',
    marginBottom: 8,
  },
  title: {
    margin: 0,
    fontSize: 28,
    lineHeight: 1.2,
  },
  subtitle: {
    marginTop: 8,
    marginBottom: 18,
    color: '#667085',
    fontSize: 13,
  },
  workflow: {
    display: 'flex',
    gap: 9,
    alignItems: 'center',
    flexWrap: 'wrap',
    background: '#fff',
    border: '1px solid #e4e7ec',
    borderRadius: 10,
    padding: '12px 14px',
    marginBottom: 14,
    fontSize: 12,
    color: '#667085',
  },
  card: {
    background: '#fff',
    border: '1px solid #e4e7ec',
    borderRadius: 10,
    padding: 16,
    marginBottom: 14,
  },
  selectionCard: {
    background: '#fff',
    border: '1px solid #b2ddff',
    borderRadius: 10,
    padding: 18,
    marginBottom: 14,
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 16,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: 700,
    marginBottom: 7,
  },
  meta: {
    display: 'flex',
    gap: 14,
    flexWrap: 'wrap',
    color: '#667085',
    fontSize: 12,
  },
  productTitle: {
    margin: 0,
    fontSize: 15,
    marginBottom: 5,
  },
  smallText: {
    color: '#667085',
    fontSize: 11,
    marginTop: 3,
  },
  tableWrap: {
    overflowX: 'auto',
    marginTop: 14,
    border: '1px solid #eaecf0',
    borderRadius: 8,
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 12,
  },
  th: {
    textAlign: 'left',
    padding: '9px 8px',
    background: '#f9fafb',
    borderBottom: '1px solid #eaecf0',
    whiteSpace: 'nowrap',
  },
  td: {
    padding: '10px 8px',
    borderBottom: '1px solid #f2f4f7',
    whiteSpace: 'nowrap',
  },
  rankBadge: {
    display: 'inline-flex',
    width: 28,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 999,
    background: '#ecfdf3',
    color: '#027a48',
    fontWeight: 700,
  },
  rankBadgeNormal: {
    display: 'inline-flex',
    width: 28,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 999,
    background: '#f2f4f7',
    color: '#475467',
    fontWeight: 700,
  },
  emptyState: {
    padding: 20,
    marginTop: 14,
    textAlign: 'center',
    color: '#667085',
    background: '#f9fafb',
    borderRadius: 8,
  },
  selectionHint: {
    marginTop: 0,
    color: '#667085',
    fontSize: 13,
  },
  selectedInfo: {
    padding: '10px 12px',
    marginBottom: 14,
    borderRadius: 8,
    background: '#eff8ff',
    color: '#175cd3',
    border: '1px solid #b2ddff',
    fontSize: 13,
  },
  poCard: {
    background: '#fff',
    border: '1px solid #98a2b3',
    borderRadius: 10,
    padding: 18,
    marginBottom: 14,
  },
  label: {
    display: 'block',
    marginBottom: 6,
    fontSize: 13,
    fontWeight: 600,
  },
  input: {
    width: '100%',
    boxSizing: 'border-box',
    border: '1px solid #d0d5dd',
    borderRadius: 8,
    padding: '10px 12px',
    fontSize: 13,
    marginBottom: 14,
  },
  textarea: {
    width: '100%',
    boxSizing: 'border-box',
    border: '1px solid #d0d5dd',
    borderRadius: 8,
    padding: '10px 12px',
    fontSize: 13,
    resize: 'vertical',
    minHeight: 100,
  },
  actions: {
    display: 'flex',
    gap: 10,
    marginTop: 14,
    flexWrap: 'wrap',
  },
  primaryButton: {
    border: '1px solid #175cd3',
    background: '#175cd3',
    color: '#fff',
    borderRadius: 8,
    padding: '10px 14px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  secondaryButton: {
    border: '1px solid #d0d5dd',
    background: '#fff',
    color: '#344054',
    borderRadius: 8,
    padding: '10px 14px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  success: {
    padding: '12px 14px',
    marginTop: 14,
    borderRadius: 8,
    background: '#ecfdf3',
    color: '#027a48',
    border: '1px solid #abefc6',
    fontSize: 13,
  },
  error: {
    padding: '12px 14px',
    marginTop: 14,
    borderRadius: 8,
    background: '#fef3f2',
    color: '#b42318',
    border: '1px solid #fecdca',
    fontSize: 13,
  },
};
