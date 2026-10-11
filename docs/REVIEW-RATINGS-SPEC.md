# Review & Ratings — Texniki Spesifikasiya

- Sənəd versiyası: 0.1
- Status: Accepted MVP contract — implemented and merged
- Tarix: 2026-10-11
- Əsas baseline: master, merge commit 4f7369663802bd49296055694b00bf34a7d8bbc9
- Əlaqəli sənədlər: ROADMAP.md, STATUS.md, MVP-SCOPE.md

## 1. Məqsəd və sərhəd

Review & Ratings modulu tamamlanmış satınalma əməliyyatından sonra təchizatçı barədə strukturlaşdırılmış qiymətləndirməni qeydə almaq, rəyi həmin əməliyyata bağlamaq, təkrar və icazəsiz rəyləri bloklamaq və nəticəni mövcud şirkət sərhədləri daxilində göstərmək üçün nəzərdə tutulur.

Bu sənəd Review & Ratings MVP üçün qəbul edilmiş texniki müqaviləni təsvir edir. Hazırkı müqavilə tenant-səviyyəli təchizatçı kataloqu və tamamlanmış Purchase Order üzrə bir ümumi rəy modelinə əsaslanır. İctimai/qobal reputasiya və moderasiya bu scope-a daxil deyil.

## 2. Mövcud kod bazasından təsdiqlənən faktlar

Mövcud modellər, miqrasiyalar və API marşrutları yoxlanılıb. Hazırkı baseline-da review/rating modeli, ona aid miqrasiya və review API marşrutları tapılmayıb.

- PurchaseOrder modeli company_id və supplier_id saxlayır.
- Delivery modeli purchase_order_id, company_id, supplier_id, status, delivered_at və received_by saxlayır.
- Çatdırılma statusları PLANNED, DISPATCHED, IN_TRANSIT, PARTIALLY_DELIVERED, DELIVERED və CANCELLED dəyərlərini əhatə edir.
- Mövcud DB kontraktı DELIVERED statusuna keçidi sifariş elementlərinin miqdarları tam çatdırılmayınca rədd edir.
- CompanyMember cədvəli user_id və company_id əsasında şirkət üzvlüyünü müəyyən edir.
- AuditLog ümumi əməliyyat auditini saxlamaq üçün mövcuddur.
- Supplier modeli company_id ilə müəyyən şirkətin təchizatçı kataloqunda saxlanılır. Mövcud model həmin qeydi qlobal təchizatçı şirkət hesabına bağlayan canonical identifikator təqdim etmir.

Sonuncu məhdudiyyət vacibdir: hazırkı sxemə əsasən müxtəlif alıcı şirkətlərin təchizatçı reytinqlərini vahid ictimai reputasiya balında təhlükəsiz birləşdirmək mümkünlüyü təsdiqlənməyib. Qlobal reytinq tələb olunarsa, təchizatçı kataloq qeydi ilə platforma şirkət hesabları arasında ayrıca identifikasiya əlaqəsi dizayn edilməlidir.

## 3. MVP siyasəti — bu vertikal dilimdə tətbiq olunan seçimlər

Bu seçimlər MVP üçün qəbul edilmiş implementasiya çərçivəsidir. Dəyişikliklər hazırda `feature/review-ratings` branch-dədir; `master`-ə birləşdirilməyib.

| Qərar | Tövsiyə olunan ilkin seçim | Səbəb |
|---|---|---|
| Rəyin obyekti | Alıcı şirkətin öz təchizatçı kataloq qeydi | Supplier modeli tenant-səviyyəlidir. |
| Görünürlük | Yalnız həmin alıcı şirkətin daxilində | Qlobal təchizatçı identifikasiyası hazırda yoxdur. |
| Rəyi kim yaza bilər | Aktiv istifadəçi və OWNER, ADMIN və ya PROCUREMENT rolu | Mövcud satınalma/çatdırılma yazma icazələri ilə uyğundur. |
| Uyğun əməliyyat | Eyni Purchase Order üzrə ən azı bir DELIVERED çatdırılma | Mövcud DB kontraktı bu status üçün bütün sifariş miqdarlarının çatdırılmasını tələb edir. |
| Təkrar rəy | Hər Purchase Order üçün maksimum bir rəy | Təkrar bal və saxta çoxaldılmanın qarşısı alınır. |
| Reytinq | Bir ümumi tam ədəd bal, 1-dən 5-ə qədər | MVP mürəkkəb alt-reytinqlərsiz başlayır. |
| Mətn | Könüllü şərh, maksimum 2000 simvol | İstifadəçiyə mətnsiz bal vermək imkanı qalır. |
| Redaktə | Müəllifə 24 saat ərzində redaktə; hər dəyişiklik audit edilir | Səhvi düzəltmək imkanı verir və dəyişiklikləri izlənə bilən saxlayır. |
| Silinmə | Adi API ilə fiziki silinmə yoxdur | Əməliyyat izini qorumaq üçündür; moderasiya ayrıca qərardır. |
| İctimai profil və iki tərəfli rəy | Bu mərhələyə daxil deyil | Supplier qeydi hazırda satıcı şirkət hesabı ilə eyniləşdirilməyib. |

## 4. Məlumat modeli təklifi

Növbəti additive miqrasiya faylı üçün təklif olunan ad: db/migrations/014_review_ratings.sql. Fayl adı və sırası implementasiya zamanı faktiki miqrasiya zənciri ilə bir daha yoxlanmalıdır.

Yeni reviews cədvəli üçün sahələr:

| Sahə | Tip / qayda | Məqsəd |
|---|---|---|
| id | UUID, primary key, gen_random_uuid() | Rəy identifikatoru |
| company_id | UUID, NOT NULL | Alıcı şirkətin tenant sərhədi |
| purchase_order_id | UUID, NOT NULL, UNIQUE | Rəyin tək və dəyişməz əməliyyat əsası |
| supplier_id | UUID, NOT NULL | Purchase Order-dan götürülən təchizatçı kataloq qeydi |
| reviewer_user_id | UUID, NOT NULL | Rəyi yaradan şirkət üzvü |
| rating | SMALLINT, NOT NULL, CHECK 1..5 | Ümumi reytinq |
| comment | TEXT, NULL, maksimum 2000 simvol | Könüllü şərh |
| created_at | TIMESTAMPTZ, NOT NULL, DEFAULT now() | Yaradılma vaxtı |
| updated_at | TIMESTAMPTZ, NOT NULL, DEFAULT now() | Son dəyişiklik vaxtı |

Təklif olunan bütövlük qaydaları:

1. Composite foreign key (purchase_order_id, company_id, supplier_id) mövcud Purchase Order composite unique açarına bağlansın. API company_id və supplier_id-ni müştəri sorğusundan kor-koranə qəbul etməsin; Purchase Order-dan özü müəyyən etsin.
2. Composite foreign key (reviewer_user_id, company_id) CompanyMember üzvlüyünə bağlansın ki, rəy müəllifi həmin şirkətə aid olsun. Üzvlük silinməsi və tarixçə saxlanması davranışı implementasiya öncəsi mövcud FK qaydaları ilə uzlaşdırılsın.
3. purchase_order_id üzərində UNIQUE bir sifarişə yalnız bir rəy təmin etsin; paralel POST cəhdlərində də DB son müdafiə xətti olsun.
4. rating üçün 1–5 aralığı SQL CHECK ilə qorunsun. comment limiti API sxemində yoxlanılsın və DB kontraktında tətbiq ediləcəksə eyni sərhəd saxlanılsın.
5. company_id, supplier_id və created_at üzrə indekslər nəzərdən keçirilsin.
6. Miqrasiya additive və tranzaksiyalı olsun; mövcud sifariş, təchizatçı, çatdırılma və audit məlumatlarını dəyişdirməsin.

Constraint adları və composite FK-lər implementasiya zamanı mövcud PostgreSQL miqrasiyaları və CI migration smoke testi ilə yoxlanmalıdır.

## 5. API müqaviləsinin layihəsi

Bütün marşrutlar mövcud FastAPI autentifikasiyasından və aktiv şirkət üzvlüyündən istifadə etməlidir. Tenant sərhədi hər sorğuda server tərəfində müəyyən edilməlidir.

### 5.1. Rəy yaratmaq

POST /api/v1/purchase-orders/{purchase_order_id}/review

Sorğu sahələri:
- rating: tam ədəd, 1–5
- comment: optional string, maksimum 2000 simvol

Server davranışı:
- Purchase Order cari istifadəçinin şirkətinə aid olmalıdır; yad tenant obyektinin mövcudluğu açıqlanmamalıdır.
- İstifadəçi aktiv olmalı və təsdiqlənmiş yazma roluna malik olmalıdır.
- Həmin sifariş üzrə DELIVERED çatdırılma şərti yoxlanmalıdır.
- company_id və supplier_id Purchase Order-dan götürülməlidir.
- Həmin Purchase Order üçün rəy varsa, ikinci rəy rədd edilməlidir.
- Rəy yazılışı və audit hadisəsi vahid DB transaction daxilində əlaqələndirilməlidir.

Uğur: HTTP 201 və yaradılmış rəyin cavabı.

### 5.2. Sifariş üzrə rəyə baxmaq

GET /api/v1/purchase-orders/{purchase_order_id}/review

- Cari şirkət çərçivəsində həmin sifarişə aid rəyi qaytarır.
- Sifariş və ya rəy tapılmadıqda HTTP 404 qaytarır.
- Başqa tenantın rəyini identifikator dəyişdirməklə oxumağa icazə verilmir.

### 5.3. Təchizatçı kataloqu üzrə rəylərə baxmaq

GET /api/v1/suppliers/{supplier_id}/reviews?page=1&limit=100

- Supplier qeydi cari şirkətə aid olmalıdır.
- Səhifələmə mövcud list API müqaviləsi ilə uzlaşdırılmalıdır.
- Cavab üçün təklif olunan sahələr: items, total, page, limit, pages, average_rating və rating_count.
- average_rating iki onluq mərtəbəyə yuvarlaqlaşdırıla bilər; rəy yoxdursa null, rating_count isə 0 olur.
- Reytinq yalnız həmin tenantın təchizatçı qeydi üzrə hesablanmalıdır.

### 5.4. Rəyi redaktə etmək — siyasət təsdiqlənərsə

PATCH /api/v1/purchase-orders/{purchase_order_id}/review

Bu marşrut yalnız 3-cü bölmədəki 24 saatlıq siyasət təsdiqlənərsə tətbiq edilir. Müəllifdən başqa istifadəçi redaktə edə bilməz; müddət keçibsə HTTP 409 qaytarılır. Hər dəyişiklik audit izini saxlayır.

### 5.5. Sifarişlər üzrə batch rəy xülasəsi

POST /api/v1/reviews/summary

Sorğu:
- purchase_order_ids: cari tenant daxilində yoxlanılan Purchase Order UUID-lərinin siyahısı; 1–10000 ID.
- Endpoint yalnız cari şirkətə aid sifarişlərdən rəy və təchizatçı reytinq xülasəsi qaytarır; yad tenantın sifariş ID-si nəticələrdə məlumat yaratmır.
- Cavab items massivində verilən sifarişlər üzrə mövcud rəylər, supplier_stats massivində isə həmin sifarişlərin təchizatçıları üzrə orta bal və rəy sayı verilir.
- Frontend bu batch endpoint-dən istifadə etməlidir; hər sifariş üçün ayrıca rəy-detal sorğusu göndərilməməlidir.

## 6. HTTP xətaları və kontrakt

| Vəziyyət | Təklif olunan HTTP |
|---|---:|
| Uğurlu rəy yaradıldı | 201 |
| Uğurlu oxuma/redaktə | 200 |
| Səhv format, bal 1–5 xaricində, çox uzun mətn | 422 |
| Autentifikasiya yoxdur | 401 |
| Rol əməliyyata icazə vermir | 403 |
| Sifariş/təchizatçı/rəy cari tenant daxilində tapılmır | 404 |
| Sifariş uyğun tamamlanma mərhələsində deyil | 409 |
| Sifariş üçün rəy artıq mövcuddur | 409 |
| 24 saatlıq redaktə müddəti bitib | 409 |

Xəta cavabları istifadəçiyə Azərbaycan dilində aydın mesaj verməli, SQL detallarını və digər tenantların məlumatlarını açıqlamamalıdır.

## 7. Audit, təhlükəsizlik və paralel sorğular

- Rəy yaradılması üçün sabit audit action adı seçilsin, məsələn REVIEW_CREATED.
- Redaktə təsdiqlənərsə REVIEW_UPDATED hadisəsi əvvəlki və yeni reytinqi, icazəli metadata çərçivəsində qeydə alsın; şərhin tam mətnini audit metadata-sına lazımsız şəkildə köçürməsin.
- Audit user_id, company_id, entity_type=REVIEW, entity_id və əməliyyat vaxtını ehtiva etsin.
- Bir Purchase Order üçün UNIQUE constraint paralel POST sorğularında təkrar yaratmanı bloklasın; uniqueness xətası HTTP 409-a çevrilsin.
- Hər oxu/yazı sorğusu tenant scope ilə filtr olunsun. İdentifikatoru bilmək təkbaşına icazə deyil.
- Rating və comment dəyərləri frontend deyil, backend tərəfindən yoxlanmalıdır.
- Şərh plain text kimi göstərilsin; istifadəçi mətni HTML kimi icra olunmasın.
- Orta reytinq yalnız təsdiqlənmiş görünürlük sərhədi daxilində hesablanmalıdır.

## 8. Frontend müqaviləsi

Təklif olunan frontend marşrutu: /reviews. Mövcud Purchase Order və ya çatdırılma kontekstindən uyğun əməliyyat üçün “Təchizatçını qiymətləndir” girişi göstərilsin.

- Yalnız uyğun, hələ qiymətləndirilməmiş Purchase Order üçün rəy forması aktiv olur.
- 1–5 bal seçimi və könüllü şərh sahəsi göstərilir.
- Uyğun olmayan status, artıq yazılmış rəy və icazə xətaları Azərbaycan dilində izah olunur.
- Yüklənmə, boş nəticə, uğur, validasiya xətası və 401/403 halları ayrıca idarə olunur.
- Orta bal və rəy sayı yalnız təsdiqlənmiş görünürlük siyasəti daxilində göstərilir.
- Frontend hesablamaları istifadə rahatlığı üçündür; son qərarı API verir.
- Dashboard-a ayrıca naviqasiya yalnız rəy reyestri ekranı təsdiqlənərsə əlavə edilir.

## 9. Avtomatlaşdırılmış test matrisi

Backend testləri ən azı aşağıdakı halları əhatə etməlidir:

1. Aktiv və icazəli alıcı üzvü uyğun tamamlanmış sifariş üzrə rəy yarada bilir.
2. DELIVERED çatdırılması olmayan sifariş üçün rəy rədd edilir.
3. Başqa şirkətin Purchase Order identifikatoru HTTP 404 ilə cavablandırılır.
4. OWNER/ADMIN/PROCUREMENT siyahısından kənar rolun rəy yazması bloklanır.
5. Bal 0, 6, mənfi və tam olmayan ədədi dəyərlər qəbul edilmir.
6. 2000 simvoldan uzun şərh qəbul edilmir; boş şərh razılaşdırılmış qaydaya uyğun normallaşdırılır və ya rədd edilir.
7. Eyni Purchase Order üçün ikinci rəy HTTP 409 alır.
8. Paralel rəy yaratma cəhdi yalnız bir rəy və bir uğurlu yaradılma ilə nəticələnir.
9. Supplier review list və average_rating tenant sərhədini aşmır.
10. Rəy yaratma audit hadisəsi yaradır; uğursuz cəhd uğurlu REVIEW_CREATED auditi yazmır.
11. Redaktə siyasəti təsdiqlənərsə müəllif, rol və 24 saat sərhədi test edilir.
12. Miqrasiya PostgreSQL 16 boş test bazasına tətbiq olunur; constraint/index smoke yoxlamasından və bütün mövcud 211 backend testindən keçir.

Frontend qəbul testləri:
- uyğun sifarişdən formanın açılması və rəy göndərilməsi;
- artıq rəy yazılmış sifarişdə təkrar göndərişin bloklanması;
- server xətalarının Azərbaycan dilində görünməsi;
- tenant icazəsi olmayan məlumatın göstərilməməsi;
- production build və təhlükəsizlik auditinin uğurlu olması.

## 10. Qəbul şərtləri və buraxılış ardıcıllığı

Implementasiyaya başlamazdan əvvəl:
1. Product Owner 11-ci bölmədəki P0 qərarları təsdiq edir.
2. DB migration dizaynı və tenant isolation modeli design review-dan keçir.
3. Backend, migration, audit və frontend testləri yazılır.
4. CI-da dörd keyfiyyət qapısı — backend regression, PostgreSQL migration smoke, frontend production build/security audit və repository hygiene — uğurla keçir.
5. Lokal integration acceptance tamam çatdırılmış test sifarişi ilə aparılır; production verilənləri dəyişdirilmir.
6. Status və qəbul sübutları yenilənir; yalnız bundan sonra release nəzərdən keçirilir.

## 11. Bu MVP dilimi üçün qərarlar

| Mövzu | MVP qərarı |
|---|---|
| Görünürlük | Yalnız alıcı şirkətin öz təchizatçı kataloqu daxilində; ictimai/qlobal reytinq yoxdur. |
| Rəyin obyekti | Hər Purchase Order üçün maksimum bir ümumi rəy. |
| Uyğunluq şərti | Eyni sifariş üzrə ən azı bir `DELIVERED` çatdırılma qeydi olmalıdır. |
| Rəyi kim yaza bilər | Aktiv istifadəçi; şirkət rolu `OWNER`, `ADMIN` və ya `PROCUREMENT`. |
| Reytinq və mətn | Tam ədəd 1–5; könüllü plain-text şərh maksimum 2000 simvol. |
| Redaktə | Yalnız müəllif, ilk yaradılmadan 24 saat ərzində; hər dəyişiklik audit edilir. |
| Silinmə və moderasiya | Adi fiziki silinmə və moderator paneli yoxdur; ictimai yayımlama bu mərhələyə daxil deyil. |

Bu qərarlar gələcəkdə dəyişdirilə bilər, lakin hər hansı qlobal/ictimai reputasiya modeli üçün supplier identifikasiyası, görünürlük və moderasiya ayrıca dizayn edilməlidir.

## 12. İcra və buraxılış statusu

- Migration: `014_review_ratings.sql`; additive, mövcud biznes sətirlərini dəyişdirmir.
- Backend: tenant-scoped create/read/list/update marşrutları, rating/comment validasiyası, duplicate prevention, RBAC, 24 saat redaktə pəncərəsi və audit.
- Frontend: `/reviews`, dashboard keçidi, şirkət rolu üzrə yazma icazəsinin göstərilməsi və çatdırılmalar üzrə server-side səhifələmə. UI hər səhifədə maksimum 100 çatdırılma sorğulamalı; bütün qalan səhifələri paralel şəkildə çağırmamalıdır.
- Quality gates: backend regression, PostgreSQL migration smoke, frontend production build/security audit və repository hygiene.
- Merge: PR #2, commit `4f7369663802bd49296055694b00bf34a7d8bbc9`.
- Pre-merge CI Run `38167889764` and post-merge CI Run #111 (`38169190885`): all four quality gates passed; backend regression 221 passed, 56 dependency deprecation warnings, no failures.
- Manual browser acceptance: review create/list/edit succeeded; rating 4/5 and updated comment remained visible; `POST /api/v1/reviews/summary` returned HTTP 200.
- Codex review of head `0309e80` found no major issues. Both rate-limit findings were addressed and the review threads resolved.
