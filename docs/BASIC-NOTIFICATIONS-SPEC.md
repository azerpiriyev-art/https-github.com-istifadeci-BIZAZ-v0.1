# Basic Notifications — Texniki Müqavilə (MVP)

- Sənəd versiyası: 0.1
- Status: **APPROVED MVP CONTRACT — implementation in progress**
- Tarix: 2026-10-11
- Dizayn bazası: `master`, commit `848c866154c28858b30ada8f05920b061b333e8c`
- Product Owner approval: confirmed in conversation on 2026-10-11
- Scope: yalnız şirkətdaxili in-app bildirişlər; bu sənəd implementasiya deyil.

## 1. Məqsəd

Mövcud BIZAZ satınalma, Approval, Purchase Order, Delivery və Payment axınlarında istifadəçinin diqqət tələb edən hadisələri görə bilməsi. Bildirişlər yalnız autentifikasiya olunmuş istifadəçinin cari şirkət/membership sərhədi daxilində göstərilir.

## 2. MVP qərarları (təklif)

1. **Kanal:** yalnız tətbiqdaxili bildiriş. E-poçt, SMS, push, WhatsApp və real-time WebSocket bu scope-a daxil deyil.
2. **İdentiklik sərhədi:** alıcı mövcud `users` + `company_members` əlaqəsindən müəyyən edilir. Supplier kataloqundakı qeyd qlobal supplier hesabına canonical şəkildə bağlanmadığından xarici supplier istifadəçilərinə bildiriş göndərilmir.
3. **İstifadəçi:** yalnız aktiv istifadəçi və cari şirkətin aktiv membership-i.
4. **Oxunma vəziyyəti:** `read_at IS NULL` oxunmamış deməkdir; mark-as-read təkrarlansa da təhlükəsiz və idempotent olmalıdır.
5. **Dil və payload:** başlıq və mətn Azərbaycan dilində, plain text; mətn HTML kimi render edilmir. Bildiriş mesajına məxfi qeydlər, token, credential və lazımsız maliyyə detalları daxil edilmir.
6. **Saxlanma:** təklif olunan müddət 180 gündür; bu qərar Product Owner tərəfindən təsdiqlənməli, implementasiyada gündəlik təmizləmə işi və onun əməliyyat sahibi də müəyyən edilməlidir.
7. **Silinmə:** istifadəçi inbox-dan bildiriş silə bilməz; 180 günlük retention mexanizmi və şirkət/üzvlük silinməsi ayrıca idarə olunur. “Hamısını oxunmuş et” MVP-yə daxil deyil.

## 3. Hadisələr və alıcıların müəyyənləşdirilməsi

Bildiriş yalnız mənbə əməliyyatı uğurla commit olduqda yaranır. Uğursuz/rollback edilmiş əməliyyat bildiriş yaratmamalıdır.

| Event type | Trigger | Alıcılar |
|---|---|---|
| `APPROVAL_ACTION_REQUIRED` | Approval step yaradılır və ya ardıcıl axında növbəti real action step aktiv olur | `approver_user_id` varsa həmin istifadəçi; yoxdursa yalnız cari approval qaydası üzrə uyğun `approver_role`-a malik aktiv company member-lər. Ardıcıl approval-da gələcək, hələ aktiv olmayan step-lər bildiriş almır. |
| `APPROVAL_DECISION_RECORDED` | Approval step üzrə qərar uğurla qeydə alınır | `ApprovalRequest.requested_by`; qərarı verən eyni istifadəçiyə bildiriş göndərilmir. |
| `PURCHASE_REQUEST_STATUS_CHANGED` | Purchase Request statusu dəyişir | `PurchaseRequest.requested_by`; hadisəni edən şəxs requester-in özü olduqda təkrar bildiriş göndərilmir. |
| `SUPPLIER_OFFER_SUBMITTED` | Supplier Offer `SUBMITTED` vəziyyətinə uğurla keçir | Həmin şirkətdəki aktiv `OWNER`, `ADMIN`, `PROCUREMENT` üzvləri; əməliyyatı edən istifadəçi istisna edilir. |
| `PURCHASE_ORDER_STATUS_CHANGED` | Purchase Order statusu dəyişir | Həmin şirkətdəki aktiv `OWNER`, `ADMIN`, `PROCUREMENT` üzvləri; əməliyyatı edən istifadəçi istisna edilir. |
| `DELIVERY_STATUS_CHANGED` | Delivery statusu dəyişir | Həmin şirkətdəki aktiv `OWNER`, `ADMIN`, `PROCUREMENT` üzvləri; əməliyyatı edən istifadəçi istisna edilir. |
| `PAYMENT_STATUS_CHANGED` | Payment statusu dəyişir | Həmin şirkətdəki aktiv `OWNER`, `ADMIN`, `FINANCE`, `PROCUREMENT` üzvləri; əməliyyatı edən istifadəçi istisna edilir. |

Qaydalar:
- Bütün alıcılar mənbə əməliyyatının `company_id` dəyərindən hesablanır; müştəri tərəfindən göndərilən `company_id` qəbul edilmir.
- Bir hadisə üzrə alıcılar təkrarlanmır; bir istifadəçi eyni hadisədə bir bildiriş alır.
- Aktiv membership-i olmayan istifadəçiyə yeni bildiriş yazılmır.
- Approval recipient-ləri mövcud `ApprovalStep` assignment və approval engine qaydaları əsasında həll edilir; burada yeni approval policy yaradılmır.
- Supplier identity mapping və xarici supplier inbox bu MVP-nin non-goal-udur.

## 4. Məlumat modeli

Yeni PostgreSQL cədvəli: `notifications` (təklif olunan migration: `015_notifications.sql`).

Minimum sütunlar:
- `id UUID PRIMARY KEY`
- `company_id UUID NOT NULL`
- `recipient_user_id UUID NOT NULL`
- `event_type VARCHAR(50) NOT NULL`
- `title VARCHAR(200) NOT NULL`
- `body VARCHAR(1000) NOT NULL`
- `source_entity_type VARCHAR(50) NOT NULL`
- `source_entity_id UUID NOT NULL`
- `source_event_key VARCHAR(180) NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `read_at TIMESTAMPTZ NULL`

Constraints and indexes:
- Composite FK `(recipient_user_id, company_id) -> company_members(user_id, company_id)`, membership silindikdə bildirişlərin həmin membership-ə aid sətirləri cascade qaydası ilə silinə bilər.
- Mənbə event üçün idempotency: `UNIQUE(company_id, recipient_user_id, source_event_key)`.
- `event_type` yalnız Bölmə 3-dəki dəstəklənən dəyərləri qəbul edir.
- `title` boş ola bilməz; `body` və bütün mətn sahələri müəyyən edilmiş uzunluq limitlərinə tabedir.
- Inbox indeksi: `(company_id, recipient_user_id, created_at DESC, id DESC)`; oxunmamış sorğular üçün `read_at IS NULL` partial index nəzərdən keçirilsin.
- Bildiriş payload-ına bütöv source entity, audit metadata və ya JSON snapshot kopyalanmır.

## 5. Transaction və idempotency

- Bildiriş yaratma mənbə domain hadisəsi və həmin hadisənin audit yazısı ilə eyni verilənlər bazası transaction-ında icra olunur.
- `source_event_key` mənbə event-in sabit identifikatorudur (məsələn audit-event ID-si və ya yaradılmış approval-step ID-si + action növü); retry eyni event üçün əlavə inbox sətirləri yaratmır.
- `ON CONFLICT DO NOTHING` və ya ekvivalent unikal məhdudiyyət davranışı duplicate delivery-ni bloklayır.
- Notification insert-i uğursuz olarsa, əməliyyatın transaction strategiyası qismən vəziyyət yaratmamalıdır; implementasiya source state, audit və bildirişi birlikdə commit/rollback edir.
- Bildirişin oxunması business entity statusunu dəyişmir.

## 6. API müqaviləsi

### GET `/api/v1/notifications?page=1&limit=20&unread_only=false`

- Cari şirkətdə yalnız cari istifadəçinin bildirişlərini qaytarır.
- `page >= 1`; `limit` default 20, minimum 1, maksimum 100.
- Cavab: `items`, `total`, `page`, `limit`, `pages`.
- `items`: `id`, `event_type`, `title`, `body`, `source_entity_type`, `source_entity_id`, `created_at`, `read_at`.
- Sıralama: `created_at DESC, id DESC`.

### GET `/api/v1/notifications/unread-count`

- Cari istifadəçi və cari şirkət üçün oxunmamış bildirişlərin sayını qaytarır: `{ "count": n }`.

### PATCH `/api/v1/notifications/{notification_id}/read`

- Yalnız recipient özü öz bildirişini oxunmuş kimi işarələyə bilər.
- İlk çağırışda `read_at` set edilir; təkrar çağırış eyni nəticəni qaytaran idempotent əməliyyatdır.
- Başqa tenant-a və ya başqa recipient-ə aid ID üçün məlumat sızdırmamaq məqsədilə `404` qaytarılır.
- Heç bir API istifadəçiyə bildiriş yaratmaq, başqa alıcının bildirişini oxumaq/silmək və ya read-state-i geriyə qaytarmaq imkanı vermir.

## 7. Frontend

- Yeni `/notifications` səhifəsi və dashboard keçidi.
- Oxunmamış say dashboard keçidində/badge-də göstərilir; səhifə açıldıqda və bildiriş oxunmuş ediləndə say yenilənir. Real-time push/polling bu MVP üçün tələb deyil.
- Siyahı səhifələnmişdir; hərəkətlər Azərbaycan dilindədir.
- Loading, boş inbox, xəta, oxunmamış/oxunmuş vəziyyətlər aydın göstərilir.
- Yalnız məlum, mövcud tətbiq route-ları üçün keçid yaradılır; naməlum entity linkləri kliklənən URL kimi uydurulmur.
- Bədən plain text kimi göstərilir; HTML icrası yoxdur.

## 8. Audit və məxfilik

- Mövcud domain event-in audit yazısı həmin event-in bildirişlərinin yaradılmasını da izah etməlidir; ayrıca audit hadisələri ən azı `NOTIFICATION_MARKED_READ` üçün qeydə alınır.
- Bildiriş mətni tam domain payload-ı və ya həssas maliyyə məlumatlarını təkrar etmir.
- Bütün list/count/update sorğuları `current_user`, cari membership, `company_id` və `recipient_user_id` ilə server-side məhdudlaşdırılır.
- API client-in göndərdiyi `company_id` alıcı icazəsini müəyyənləşdirmək üçün istifadə edilmir.

## 9. Qəbul meyarları

- [ ] Hər dəstəklənən event növü yalnız uğurlu domain transaction-dan sonra bildiriş yaradır.
- [ ] Approval action bildirişi yalnız real olaraq hərəkət gözləyən step-lərə gedir; ardıcıl gələcək step-lər erkən bildiriş almır.
- [ ] Alıcı resolvers aktiv membership və event-ə uyğun role/user assignment istifadə edir; actor-exclusion qaydası qorunur.
- [ ] Təkrar/retry event bir recipient üçün duplicate bildiriş yaratmır.
- [ ] Başqa şirkətin və ya başqa recipient-in bildirişini oxumaq/count etmək/mark-as-read etmək mümkün deyil.
- [ ] Unread count, pagination, sıralama, idempotent mark-as-read və 404 isolation testləri var.
- [ ] Retention planı və gündəlik purge mexanizmi əməliyyat prosedurunda dəqiqləşdirilib; 180 günlük təklif təsdiqlənib.
- [ ] Azerbaijani UI loading/empty/error/read/unread halları ilə browser acceptance keçir.
- [ ] Full backend regression, PostgreSQL migration smoke, frontend production build/security audit, repository hygiene — dörd CI gate-in hamısı keçir.

## 10. Scope-dan kənar

- E-mail/SMS/push/WhatsApp/real-time WebSocket.
- Qlobal supplier identity və başqa tenant-a aid istifadəçilərə bildirişlər.
- İstifadəçi tərəfindən bildiriş silmə, “hamısını oxunmuş et”, moderator paneli.
- Bildiriş analitikası və KPI dashboard inteqrasiyası.

## 11. Təsdiqlənmiş Product Owner qərarları

Product Owner aşağıdakı MVP siyasətlərini təsdiqləyib:
1. Bildirişlər 180 gün saxlanılır; gündəlik purge əməliyyatının məsul rolu BIZAZ sistem administratorudur.
2. Bölmə 3-dəki event trigger-ləri və rol əsaslı alıcı siyahıları qəbul edilib.
3. Bildiriş insert-i uğursuz olarsa, source domain dəyişikliyi, audit və notification eyni transaction-da rollback edilir.
4. MVP yalnız in-app bildirişlərdən ibarətdir. E-poçt/SMS/push və xarici supplier user bildirişləri scope-dan kənardır.
