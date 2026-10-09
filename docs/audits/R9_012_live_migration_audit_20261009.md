# BIZAZ — R9 Live Migration Audit

**Tarix:** 2026-10-09
**Mərhələ:** R9 — Purchase Order Status Contract
**Nəticə:** Texniki yoxlamalar uğurludur

## 1. Mənbə və versiya

- Git commit: `37ce745caaaec180c5b318f7ab6f1f683b525373`
- Migration: `db/migrations/012_purchase_order_status_contract_hardening.sql`
- Migration SHA-256: `27AFF19C19884396D3282B66A2D2836C749D6B91A90230EDEE415FFC38547C9A`
- CI run: https://github.com/azerpiriyev-art/https-github.com-istifadeci-BIZAZ-v0.1/actions/runs/37932195926
- CI nəticəsi: success

## 2. Canlı baza üçün ehtiyat nüsxə

- Baza: `bizaz`
- Fayl: `%LOCALAPPDATA%\Temp\BIZAZ_LIVE_PRE_012_20261009_164928\bizaz_live_pre_012_20261009_164928.dump`
- SHA-256: `9E61C7B1264B46AFE6BD9A6E86A9D86D68BF857E2848AE8934FBEBFDA58F405E`
- Arxiv siyahısı `pg_restore -l` ilə yoxlanılıb.
- Host və konteyner SHA-256 dəyərləri uyğun gəlib.
- Tam bərpa sınağı bu mərhələdə aparılmayıb.

## 3. Migration tətbiqi

Migration `bizaz` bazasına tətbiq olunub. Əməliyyat `BEGIN`, `CREATE FUNCTION`, `CREATE TRIGGER`, yoxlama bloku və `COMMIT` ilə tamamlanıb.

Migration-dan sonra:
- `fn_validate_purchase_order_state`: 1 funksiya
- Status validasiyası trigger-i: 1 trigger

## 4. Canlı baza üzrə nəticələr

Migration-dan əvvəl və sonra sifariş göstəriciləri eyni qalıb.

| Status | Sifariş sayı |
|---|---:|
| DRAFT | 157 |
| SUBMITTED | 24 |
| RECEIVED | 46 |
| CANCELLED | 31 |
| Cəmi | 258 |

- Çatdırılmalar: 0
- Sifarişlərin ümumi sayı dəyişməyib.
- Canlı rollback testlərindən sonra status bölgüsü dəyişməyib.

## 5. Canlı rollback testləri

Mövcud sifarişlə, bir tranzaksiya daxilində aparılmış sınaqlar:

- DRAFT -> SUBMITTED -> APPROVED -> RECEIVED: PASS
- RECEIVED -> APPROVED: rədd edildi, PASS
- Eyni statusun təkrar təyin edilməsi: rədd edildi, PASS
- CANCELLED -> DRAFT: rədd edildi, PASS
- Sınaq tranzaksiyası: ROLLBACK

Bu sınaqlar real sifariş dəyişikliyini saxlamayıb.

## 6. Ayrı test mühitində

- Test bazası: `bizaz_procurement_test`
- CI migration smoke test və digər CI işləri: PASS
- Backend regressiya dəsti: 205 test keçib
- Purchase Order status contract testləri: 6 test keçib
- Test hesabı ilə login: PASS
- `GET /api/v1/products`: PASS

Test backend-i `bizaz_procurement_test` bazasından istifadə edir. Bu, canlı `bizaz` bazasına qarşı API sınağı kimi qəbul edilmir.

## 7. API yoxlamaları

Port: `127.0.0.1:8001`

- `GET /health`: HTTP 200
- `GET /api/v1/meta`: HTTP 200
- `GET /openapi.json`: HTTP 200

## 8. Məhdudiyyətlər və növbəti addımlar

- Canlı bazada ayrıca tam tətbiq regressiya dəsti icra edilməyib; bu, istehsal məlumatlarının təhlükəsizliyi üçün qəsdən belə saxlanılıb.
- Backup arxivinin oxuna bilməsi təsdiqlənib, tam bərpa sınağı isə açıq qalır.
- Növbəti mərhələ: ayrı test bazasında satınalma sifarişi və çatdırılma axınının API inteqrasiya sınaqları.
- Migration 012 təkrar tətbiq edilməməlidir; canlı bazada trigger və funksiya artıq mövcuddur.
