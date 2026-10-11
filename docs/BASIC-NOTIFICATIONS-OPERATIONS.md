# Basic Notifications — Əməliyyat Təlimatı

Status: feature implementation draft; tətbiq yalnız release/merge-dən sonra canlı istifadə üçün uyğundur.

## Saxlanma və gündəlik purge

- Qəbul edilmiş siyasət: bildirişlər yaradılma vaxtından 180 gün saxlanılır.
- Əməliyyat sahibi: BIZAZ sistem administratoru.
- Script: `backend/scripts/purge_expired_notifications.py`.
- Script yalnız `notifications` cədvəlində `created_at < now() - INTERVAL '180 days'` olan sətirləri silir; business, audit və digər cədvəlləri dəyişmir.
- Script DB əməliyyatını transaction daxilində icra edir və silinən sətirlərin sayını stdout-a yazır. Təmizləmə uğursuz olarsa, transaction commit edilmir və proses qeyri-sıfır xəta ilə dayanmalıdır.

## Windows Task Scheduler ilə qeydiyyat

1. Layihə buraxıldıqdan sonra server administratoru Task Scheduler-də gündəlik task yaradır.
2. Program: `C:\Projects\BIZAZ-v0.1\backend\venv\Scripts\python.exe`
3. Arguments: `C:\Projects\BIZAZ-v0.1\backend\scripts\purge_expired_notifications.py`
4. Start in: `C:\Projects\BIZAZ-v0.1\backend`
5. Gündə bir dəfə, aşağı yüklü vaxtda başladın. Dəqiq saat deployment runbook-da təsdiqlənməli və seçilmiş server timezone-u ilə sənədləşdirilməlidir.
6. Task yalnız DB-yə tələb olunan icazəsi olan ayrıca servis hesabı altında işləməlidir. Heç bir parol/secret task argument-lərində saxlanmamalıdır; DB connection mövcud server secret/config mexanizmi ilə təmin olunmalıdır.

## Əməliyyat yoxlaması

- Task-in Last Run Result uğurlu olmalıdır.
- Çıxışdakı `deleted=n` sayını log-da saxlayın; credentials və bildiriş mətnlərini log-a yazmayın.
- Task uğursuz olduqda BIZAZ sistem administratoru xətanı araşdırmalı, düzəlişdən sonra task-i bir dəfə əl ilə test etməlidir.
- Bu task-ın faktiki production host-da quraşdırıldığı iddiası yalnız hostda yoxlandıqdan sonra qeyd edilə bilər.
