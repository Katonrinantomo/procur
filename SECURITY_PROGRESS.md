# Procur.AI: Progress Keamanan (Fase 0 dan Fase 1)

Branch: `security` | Tanggal: 24 Oktober 2026 | Penanggung jawab: Agiel (Security / Backend hardening)

Dokumen ini merangkum apa yang sudah dikerjakan di sisi keamanan, cara memverifikasinya, dan apa yang masih terbuka. Konteks: aplikasi didemokan di **localhost** dengan LLM lewat **9router**, sehingga prioritas ada pada penutupan akses jaringan, validasi input dari AI/web, dan ketahanan layar saat demo.

> Logika perhitungan harga dan flag (`backend/app/services/pricing.py`, `flags.py`) **tidak diubah** sama sekali.

---

## Ringkasan

| Fase | Fokus | Status |
|---|---|---|
| Fase 0 | Infrastruktur dan binding jaringan | Selesai |
| Fase 1 | Hardening kode (7 butir) | Selesai, 232 test lulus (43 test baru) |
| Fase 2 | Login, peran maker/checker, audit log | Belum dikerjakan |
| Fase 3 | CI scanning, threat model STRIDE | Belum dikerjakan |

---

## Fase 0: Infrastruktur

| Perubahan | Berkas | Dampak |
|---|---|---|
| `start.sh` ditulis ulang: tiap service jalan di grup proses sendiri (`setsid`), cek port bentrok sebelum start, health check backend/frontend/Langflow, lokasi Langflow lewat variabel `LANGFLOW_DIR` (default `~/langflow`) | `start.sh` | Langflow sebelumnya gagal start diam-diam karena dijalankan dari folder yang bukan proyek uv |
| `stop.sh` mematikan seluruh grup proses, bukan hanya pembungkusnya, lalu menampilkan sisa proses | `stop.sh` | Sebelumnya proses anak (Vite, Langflow) menumpuk setelah beberapa kali start/stop |
| Langflow dijalankan dengan `--host 127.0.0.1` | `start.sh` | Tidak terbuka ke jaringan |
| Port PostgreSQL dipetakan ke `127.0.0.1:5432:5432` | `docker-compose.yml` | Sebelumnya `0.0.0.0:5432`, terjangkau dari jaringan yang sama (terkait SEC-09) |
| Tambah `.ob1/`, `.bob/`, `*.db`, `*.sqlite` | `.gitignore` | Mencegah sesi agent dan file database ikut ter-commit (SEC-16, SEC-17) |

Pengecekan yang dilakukan:

- Binding diverifikasi dengan `ss -ltn`: Vite `127.0.0.1:5173`, backend `127.0.0.1:8000`, Langflow `127.0.0.1:7860`, PostgreSQL `127.0.0.1:5432`.
- Versi Langflow **1.12.2**, jauh di atas versi yang terkena CVE-2025-3248.
- Export flow (`langflow/Organize.json`, `langflow/Web Check.json`) di-grep untuk pola key/secret: tidak ada nilai kredensial. Model dan provider (9router) dipilih saat runtime, bukan disimpan di JSON.

---

## Fase 1: Hardening kode

| # | Commit | Temuan | Perubahan | Perilaku yang terlihat |
|---|---|---|---|---|
| 1 | `764a466` | SEC-10, C2 | `security.py` berisi `safe_http_url()` (hanya http/https dengan hostname valid, maks 2048 karakter). Dipakai di `web_check.py` sebelum simpan, dan di `WebQuotesTable.tsx` / `SupplierPanel.tsx` sebelum render. Placeholder URL di seed dibersihkan | URL tidak valid (`javascript:`, `file:`, placeholder) disimpan `NULL` dan tampil sebagai teks biasa. Harga tetap tersimpan |
| 2 | `b839bac` | SEC-06, M2 | Upload dibaca dengan batas ukuran, cek magic bytes `.xlsx`, batas 10.000 baris per upload | File palsu berekstensi `.xlsx` ditolak (400) |
| 3 | `ae3f5c3` | SEC-04 | `check_error` hanya berisi pesan generik, traceback penuh dicatat di log server | API tidak lagi membocorkan path file atau tipe exception |
| 4 | `d757e91` | LLM10 (konsumsi berlebihan) | `max_length` pada input parse (10.000) dan quick-check (5.000) dan rate limit 10 request/menit per IP (`slowapi`) pada `/api/requests/parse`, `/api/quick-check`, `/api/request-items/{id}/recheck` | Input terlalu panjang: 422. Melebihi batas laju: 429 |
| 5 | `b8a940f` | SEC-03 | `seed --reset` menolak jalan jika `APP_ENV=production` atau host DB bukan localhost, kecuali flag `--i-know-what-i-am-doing` | Mencegah data terhapus tidak sengaja |
| 6 | `f361ec1` | SEC-02, SEC-13 (sebagian) | `TrustedHostMiddleware` (`localhost`, `127.0.0.1`), CORS dengan allowlist origin, header `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options` | Host asing (mis. `evil.example.com`) dijawab 400 |
| 7 | `c8f4aa2` | SEC-12 | `DATABASE_URL` wajib diisi, tidak ada lagi kredensial default di `config.py` | Backend berhenti saat startup dengan pesan jelas bila belum dikonfigurasi |

Catatan pelabelan: pesan commit #4 menyebut "SEC-01", padahal SEC-01 adalah **ketiadaan autentikasi**, yang belum ditangani. Commit tersebut sebenarnya menutup risiko konsumsi berlebihan pada endpoint LLM (OWASP LLM10 / API4).

### Hasil pengujian

- `pytest`: **232 lulus, 0 gagal** (43 test baru: middleware, rate limit, validasi URL, guard seed, impor file, validasi konfigurasi).
- Build frontend: bersih.
- Tidak ada test lama yang diubah agar lulus.

### Cara memverifikasi manual

```bash
./stop.sh && ./start.sh
ss -ltn | grep -E ':(7860|8000|5173|5432)\b'      # semua harus 127.0.0.1
curl -s -H "Host: evil.example.com" http://127.0.0.1:8000/api/health   # harus 400
cd backend && source .venv/bin/activate && pytest
```

---

## Cara menjalankan

```bash
export LANGFLOW_DIR=~/langflow   # folder instalasi Langflow (opsional, default ~/langflow)
./start.sh                       # menunggu sampai ketiga service merespons
./stop.sh                        # mematikan seluruh proses dan menampilkan sisa proses
```

Konfigurasi backend dibaca dari `backend/.env` (bukan root). `DATABASE_URL` wajib diisi. Jangan commit `backend/.env`.

---

## Belum dikerjakan / risiko yang diterima

| ID | Isi | Status |
|---|---|---|
| SEC-01 | Tidak ada autentikasi dan otorisasi, `approve` dan `return` tidak terikat identitas | Diterima untuk demo localhost. Rencana: Fase 2 (login, maker-checker, audit log) |
| SEC-09 | Kredensial PostgreSQL demo masih `procur`/`procur`/`procur` | Dimitigasi karena port hanya di localhost. Ganti sebelum deploy |
| SEC-13 | Content-Security-Policy belum dipasang (hanya tiga header dasar) | Terbuka |
| SEC-08 | TLS koneksi DB | Tidak relevan selama DB di mesin yang sama |
| H1 (SEC-05) | Quick Check bisa error 500 untuk barang yang benar-benar baru | Belum diperbaiki di branch ini, perlu direproduksi dengan test |
| H2 | Logika cache Web Check (fuzzy vs exact) tidak sinkron | Belum diperbaiki |
| SEC-14, 18, 19 | Skor fuzzy match terlalu longgar, wildcard `LIKE` tidak di-escape, tidak ada retry ke Langflow | Prioritas rendah |
| Langflow | Nilai `LANGFLOW_AUTO_LOGIN` belum dicek | Cek lewat jendela incognito di `http://localhost:7860` |
| Flow | Flow di repo belum tentu sama dengan flow runtime (9router) | Export ulang bila diperlukan |
| Fase 3 | `gitleaks`, `pip-audit`, `npm audit`, `bandit`, OWASP ZAP, threat model STRIDE | Belum dikerjakan |

---

## Rujukan

- OWASP ASVS, OWASP API Security Top 10 (2023), OWASP Top 10 for LLM Applications (2025)
- NIST SP 800-218 (SSDF), CIS Benchmark PostgreSQL
- STRIDE (Kohnfelder dan Garg)