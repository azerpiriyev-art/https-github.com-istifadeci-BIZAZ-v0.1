# BIZAZ — Pulsuz Pilot Server üçün Hazırlıq

Status: deployment planı; heç bir canlı server yaradılmayıb və bu sənəddəki əmrlər icra olunmayıb.

## 1. Qərar

İlk ictimai texniki pilot üçün Oracle Cloud Infrastructure (OCI) Always Free compute VM araşdırılır. Cari free-tier təklifində ARM Ampere A1 üçün aylıq 1,500 OCPU-saat və 9,000 GB-saat yaddaş limiti var; uyğun konfiqurasiya təxminən 2 OCPU və 12 GB RAM-a uyğundur. Bu resurslar yalnız home region-da Always Free limitləri daxilində saxlanıldıqda pulsuz qalır. Regionda resurs çatışmazlığı ola bilər və Always Free hesabına Oracle Support xidməti daxil deyil.

Bu, **pilot seçimidir**, uptime/SLA zəmanəti olan istehsal infrastrukturu deyil. Hələ real müştəri məlumatlarını və kritik əməliyyatları yerləşdirməyin.

## 2. Host hazırlığı

1. OCI Free Tier hesabı yaradın və home region-u diqqətlə seçin. Yalnız Always Free etiketi olan resurslardan istifadə edin; ödənişli trial resursları 30 gündən sonra davamlı pulsuz sayılmır.
2. Ubuntu ARM64 VM və boot volume yaradın. Yaradılış zamanı Always Free kvotasını və yekun ödəniş səhifəsini yoxlayın.
3. SSH girişini şəxsi public key ilə məhdudlaşdırın. Şifrə ilə root SSH girişini söndürün.
4. Cloud firewall/Security List və VM firewall-da yalnız SSH portunu öz idarəetmə IP-nizdən, TCP 80 və 443 portlarını isə ehtiyac üzrə açın. PostgreSQL 5432 portunu internetə açmayın.
5. Domenin DNS A qeydi VM-nin public IPv4 ünvanına yönəlməlidir. Caddy etibarlı HTTPS sertifikatı üçün düzgün domen və 80/443 girişinə ehtiyac duyur.

## 3. Serverdə ilkin qurulum

Aşağıdakı əmrlər təmiz Ubuntu host üçün nümunədir; əmrləri yalnız VM yaradılıb SSH ilə daxil olduqdan sonra işlədin.

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git openssl
```

Docker Engine və Compose plugin-i Docker-in Ubuntu üçün rəsmi təlimatına əsasən quraşdırın. Docker versiyasını yoxlayın:

```bash
docker --version
docker compose version
```

Sonra repozitoriyanı klonlayın və production hazırlıq branch-i yoxlamalardan keçdikdən sonra təsdiqlənmiş commit-i checkout edin. Deployment üçün təsdiqlənməmiş branch-dən və ya test konfiqurasiyasından istifadə etməyin.

## 4. Sirrlər və domen

Repo kökündə:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 64
```

Birinci nəticəni `POSTGRES_PASSWORD`, ikinci nəticəni `BIZAZ_APP_PASSWORD`, üçüncü nəticəni `JWT_SECRET` yerinə daxil edin. Nəticələri Git-ə, söhbətə, log-a və Docker image-ə yerləşdirməyin. `BIZAZ_DOMAIN` və `CORS_ORIGINS` dəyərlərini real domenə uyğun dəyişdirin. Hex parollar URL-də xüsusi simvolların kodlanması riskini aradan qaldırmaq üçün istifadə edilir.

## 5. İlkin database bootstrap

Bu bootstrap **yalnız yeni və boş PostgreSQL volume-u ilə bir dəfə** istifadə edilməlidir. Mövcud və ya məlumat olan bazada bootstrap profilini yenidən işə salmayın. Gələcək release-lər üçün yalnız review edilmiş və tətbiq edilməmiş migration faylları ehtiyat nüsxədən sonra tətbiq edilməlidir.

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d db
docker compose --env-file .env.production -f docker-compose.prod.yml --profile bootstrap run --rm bootstrap-schema
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl --fail --show-error https://YOUR_REAL_DOMAIN/health
```

`YOUR_REAL_DOMAIN` dəyərini real domenlə əvəz edin. Bütün konteynerlərin healthy/running vəziyyəti və HTTPS health endpoint-i təsdiqlənməyincə buraxılış tamamlanmış sayılmır. Məlumat bazası host portuna publish edilmir; FastAPI isə superuser olmayan ayrıca tətbiq rolundan istifadə edir.

## 6. Ehtiyat nüsxə və bərpa

- İlk real məlumat daxil edilməzdən əvvəl PostgreSQL custom-format dump yaradın və `pg_restore --list` ilə yoxlayın.
- Dump-ın SHA-256 yoxlamasını aparın və nüsxəni VM-dən kənarda, məhdud girişli saxlamaya göndərin. VM-nin öz diskindəki nüsxə təkbaşına disaster recovery üçün kifayət deyil.
- Bərpa sınağını ayrı, izolyasiya edilmiş test bazasında edin; canlı bazanın üzərinə sınaq bərpası etməyin.
- OCI Object Storage və ya başqa xarici backup hədəfinin konkret bucket, credential, retention və restore proseduru ayrıca qurulmalı və sınaqdan keçirilməlidir. Bu əməliyyatlar hələ qurulmayıb.

## 7. Bildirişlərin 180 günlük purge tapşırığı

Purge skripti FastAPI konteynerinə daxil edilir. Hostda gündəlik cron tapşırığı yalnız app konteyneri və production DB istifadəyə verildikdən, backup/restore yoxlamaları bitdikdən sonra qeydiyyata alınmalıdır. Tapşırıq `docker compose exec -T api python -m scripts.purge_expired_notifications` işlədə bilər; secret-ləri əmr sətrinə əlavə etməyin və bildiriş mətnlərini log-a yazmayın.

Qurulumdan sonra cron nəticəsi və `deleted=n` çıxışı yoxlanmalı, log rotation və uğursuzluq xəbərdarlığı konfiqurasiya edilməlidir. Hazırda task quraşdırılmayıb.

## 8. Pilotdan istehsala keçid meyarları

Ödənişli istehsal mühitinə keçid öncəsi aşağıdakılar tamamlanmalıdır:

- təsdiqlənmiş domen, TLS və təhlükəsiz hesab girişləri;
- real backup-ın hostdan kənarda saxlanması və uğurlu restore sınağı;
- monitorinq, alarm və log rotation;
- PostgreSQL miqrasiya və rollback planı;
- tenant/company isolation və autentifikasiya acceptance testləri;
- gündəlik backup və 180 günlük notification purge tapşırıqlarının uğurlu sınağı;
- aylıq xərc və istifadə limitlərinin izlənməsi.

## Rəsmi mənbələr

- OCI Free Tier: https://www.oracle.com/cloud/free/
- OCI Always Free compute resursları: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
