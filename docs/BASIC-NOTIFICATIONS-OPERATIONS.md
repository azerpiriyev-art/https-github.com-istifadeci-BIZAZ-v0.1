# Basic Notifications — Əməliyyat Təlimatı

Status: feature implemented and merged; production purge task is **not configured** because the live server has not been provisioned.

## Saxlanma və gündəlik purge

- Qəbul edilmiş siyasət: bildirişlər yaradılma vaxtından 180 gün saxlanılır.
- Əməliyyat sahibi: BIZAZ sistem administratoru.
- Script: `backend/scripts/purge_expired_notifications.py`.
- Script yalnız `notifications` cədvəlində `created_at < now() - INTERVAL '180 days'` olan sətirləri silir; business, audit və digər cədvəlləri dəyişmir.
- Script DB əməliyyatını transaction daxilində icra edir və silinən sətirlərin sayını stdout-a yazır. Təmizləmə uğursuz olarsa, transaction commit edilmir və proses qeyri-sıfır xəta ilə dayanmalıdır.

## Linux serverdə gündəlik tapşırıq

Server qurulduqdan, production konfiqurasiyası tətbiq edildikdən və backup/restore sınağı keçdikdən sonra cron tapşırığı konfiqurasiya edilməlidir. Tapşırıq hər gün aşağı yüklü vaxtda işlədilməlidir; saat və timezone deployment runbook-da qeydə alınmalıdır.

Nümunə cron sətri (repo yolu və vaxtı real deployment-a uyğunlaşdırın):

```cron
15 3 * * * cd /opt/bizaz && /usr/bin/docker compose --env-file .env.production -f docker-compose.prod.yml exec -T api python -m scripts.purge_expired_notifications >> /var/log/bizaz-notification-purge.log 2>&1
```

Şərtlər:
- `.env.production` yalnız serverdə saxlanmalı və fayl icazələri məhdudlaşdırılmalıdır.
- Tapşırıq heç bir parol və ya token-i komanda sətrinə əlavə etməməlidir.
- Log-da yalnız nəticə (məsələn, `deleted=0`) və texniki xəta olmalıdır; bildiriş mətnlərini log-a yazmayın.
- Log rotation və uğursuzluq xəbərdarlığı qurulmalıdır.
- Task işlədikdən sonra exit code, log və `deleted=n` nəticəsi yoxlanılmalıdır.
- Cron sətri sadəcə nümunədir; faktiki production host-da task quraşdırılmayıb və sınaqdan keçirilməyib.

## Windows Task Scheduler alternativi

Əgər sonradan Windows Server seçilərsə:

1. Program: `C:\Projects\BIZAZ-v0.1\backend\venv\Scripts\python.exe`
2. Arguments: `-m scripts.purge_expired_notifications`
3. Start in: `C:\Projects\BIZAZ-v0.1\backend`
4. Ayrı, minimum DB səlahiyyətləri olan servis hesabı istifadə edin; secret-ləri task argument-lərində saxlamayın.

Bu variant da faktiki hostda ayrıca quraşdırılmalı və sınaqdan keçirilməlidir.
