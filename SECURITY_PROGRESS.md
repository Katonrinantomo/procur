# Procur.AI: Progress Keamanan

Diperbarui: **2 November 2026** · Kode yang ditinjau: `main` @ `a81bc47` (branch `security` sudah digabung) · Dokumen asli: 24 Oktober 2026 (Fase 0 dan 1)

Dokumen ini adalah register temuan keamanan: apa yang sudah **SELESAI**, bukti kodenya, batasnya, dan apa yang **MASIH TERBUKA**. Statusnya sudah dicocokkan dengan kode dan tes, bukan disalin dari versi lama. Arsitektur dan matriks peran: [`ARCHITECTURE.md`](ARCHITECTURE.md) §4 dan §7. Masalah non-keamanan: [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md).

> **Konteks:** aplikasi didemokan di **localhost**. Semua service terikat ke `127.0.0.1`. Penilaian di bawah mengasumsikan itu; beberapa butir "terbuka" menjadi wajib sebelum ada deployment sungguhan.
> Logika harga dan flag (`pricing.py`, `flags.py`) tidak diubah demi keamanan. Model tidak pernah menghitung harga, persentase, skor, atau flag.

---

## Ringkasan

| Fase | Fokus | Status |
|---|---|---|
| Fase 0 | Infrastruktur dan binding jaringan | **Selesai** |
| Fase 1 | Hardening kode (7 butir) | **Selesai** |
| Fase 2 (Sektor 1) | Login JWT, peran Maker-Checker, audit log keputusan | **Selesai** (sebelumnya tertulis "belum dikerjakan") |
| Fase 3 | Pemindai kerentanan, threat model STRIDE, CI | **Belum dikerjakan** |

Hasil uji terakhir: `pytest` menghasilkan **514 lulus, 1 dilewati** dari 515 tes (yang dilewati adalah tes langsung ke Langflow, jalan dengan `-m live`). Cakupan baris 95,6% pada `app/services`.

| Status | Baris di register | Butir |
|---|---:|---|
| ✅ **SELESAI** | 15 | SEC-01, Audit logging, Maker-Checker, SEC-02, SEC-03, SEC-05, SEC-06, SEC-07, SEC-10, SEC-12, SEC-13, SEC-16/17, SEC-18, SEC-19, LLM10 |
| 🟡 **SEBAGIAN** | 2 | SEC-04 (jalur kegagalan Langflow), SEC-14 (matcher) |
| ⏳ **TERBUKA** (diterima untuk demo) | 1 | SEC-09 |
| ➖ Tidak relevan saat ini | 1 | SEC-08 |

Selain register, ada **11 risiko baru (N-01 sampai N-11)** dari tinjauan 2 November, terutama untuk persiapan produksi. Semuanya terbuka. Status "SELESAI" berarti perbaikan ada di kode dan (kecuali bila disebut) ada tesnya; kolom *Batas* di register menyebut apa yang **tidak** tercakup.

---|---:|---|
| **SELESAI** | 16 | SEC-01, 02, 03, 05, 06, 07, 10, 12, 13, 16, 17, 18, 19, LLM10, Audit logging, SEC-04 (sebagian, lihat N-01) |
| **SEBAGIAN** | 2 | SEC-04 (pesan error Langflow), SEC-14 (matcher) |
| **TERBUKA / diterima untuk demo** | 3 | SEC-08, SEC-09, dan butir N-01…N-10 di bawah |

> Hitungan di atas hanya ringkasan. Sumber kebenarannya adalah tabel register di bagian berikut.

---

## Register temuan

Legenda: ✅ SELESAI · 🟡 SEBAGIAN · ⏳ TERBUKA (diterima untuk demo) · ➖ tidak relevan saat ini

| ID | Temuan | Status | Bukti (kode → tes) | Batas yang perlu diketahui |
|---|---|---|---|---|
| **SEC-01** | Tidak ada autentikasi dan otorisasi; approve/return tidak terikat identitas | ✅ **SELESAI** | `routers/auth.py` (login, `get_current_user`, `require_roles`), `security.py` (PBKDF2 600.000 iterasi, JWT HS256 1 jam). Setiap router memakai `get_current_user` di tingkat router. → `test_auth.py` (28 tes): setiap rute 401 tanpa token, token palsu / kedaluwarsa / tanpa `sub` ditolak, matriks peran, kepemilikan baris, login dibatasi 5 per menit | Token disimpan di `localStorage` dan tidak bisa dicabut sebelum kedaluwarsa (N-03). Akun dibuat lewat seed saja, tanpa halaman manajemen pengguna (N-06) |
| **Audit logging** (Sektor 1) | Keputusan approve/return tidak tercatat | ✅ **SELESAI** | Tabel `audit_log`, satu fungsi penulis `services/decisions.record_request_item_decision`: `user_id`, `role`, keputusan, alasan, tag hasil, **potret bukti** (flag, risk score, harga referensi dan sumbernya). Status baris dan baris log ditulis dalam satu transaksi. Hanya `owner` dan `finance` yang bisa membaca (`/api/decisions`, `/api/decisions.csv`, `/api/audit-logs`). → `test_decisions.py` (26 tes): aturan override, snapshot, CSV, `AuditLogImmutableError` pada update/delete lewat ORM, tidak ada rute yang mengubah/menghapus log | Kekekalan dijaga di **lapisan ORM**; administrator database dengan SQL langsung masih bisa mengubah baris (N-04). Yang dicatat hanya **keputusan**, bukan login, impor, atau pembuatan request |
| **Maker-Checker** | Satu orang bisa mengajukan sekaligus menyetujui | ✅ **SELESAI** | `routers/request_items._decide`: 403 bila pemutus adalah pembuat request (berlaku untuk approve dan return). Approve/return khusus `owner`. Override (baris `flagged` atau risk ≥ 50) wajib alasan dan tag hasil. → `test_auth.py::TestSelfApproval403`, `test_decisions.py` | Penjaga membandingkan ID pengguna; dua akun yang bersekongkol tidak terdeteksi. Request tanpa pembuat tercatat (data seed lama) tidak punya pemeriksaan ini |
| **SEC-02** | Host header dan CORS tidak dibatasi | ✅ **SELESAI** | `main.py`: `TrustedHostMiddleware`, CORS allow-list, header `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`. → `test_middleware.py` (7 tes) | Nilai host dan origin di-hardcode untuk localhost (N-07) |
| **SEC-03** | `seed --reset` bisa menghapus data di lingkungan non-demo | ✅ **SELESAI** | `seed.py`: menolak jika `APP_ENV=production` atau host DB bukan lokal, kecuali `--i-know-what-i-am-doing`. → `test_seed_guard.py` (5 tes) | Penjaga bergantung pada variabel lingkungan yang diisi benar |
| **SEC-04** | `check_error` membocorkan path file dan tipe exception | 🟡 **SEBAGIAN** | Kegagalan tak terduga: pesan generik `"Pengecekan gagal, coba lagi nanti."`, traceback hanya di log (`checker.check_item`). Kegagalan penawaran: pesan konstan. → `test_api.py::TestCheckErrorSanitization` | **Jalur kegagalan Langflow/Serper tidak disanitasi:** `web_check` menyimpan `web_check failed: <teks exception>` ke `check_error`, dan `/api/requests/parse` mengembalikan `str(exc)` pada HTTP 502. Contoh terverifikasi: `web_check failed: Langflow call failed after 3 attempts: ConnectError(...)`. Lihat **N-01** |
| **SEC-05** | Quick Check error 500 untuk barang yang benar-benar baru | ✅ **SELESAI** | `quick_check` menjadi `def` biasa; tidak ada `session.refresh()` pada objek yang belum tersimpan. → `test_web_price_path.py::TestUnknownItemNoWebQuotes` | — |
| **SEC-06** | Unggahan tanpa batas ukuran dan tanpa validasi isi | ✅ **SELESAI** | Impor: hanya `.xlsx`/`.csv`, maks 5 MB (413), magic bytes `PK\x03\x04` untuk `.xlsx`, maks 10.000 baris. Penawaran: `.pdf`/`.xlsx`, maks 10 MB, magic bytes `%PDF-` / `PK\x03\x04`. → `test_import.py` (hardening), `test_quotations.py::test_bad_magic_400`, `test_too_large_413` | Magic bytes hanya memeriksa awal berkas; isi tetap diurai oleh `openpyxl`/`pdfplumber` |
| **SEC-07** | Tautan kutipan web palsu (placeholder) di seed | ✅ **SELESAI** | Placeholder diganti `None` di `seed.py`; tautan hasil web hanya disimpan lewat `safe_http_url` | Kutipan solenoid di seed masih **data demo** tanpa URL, tetapi UI menyebutnya "captured" (lihat `KNOWN_ISSUES.md` O-6) |
| **SEC-08** | Koneksi DB tanpa TLS | ➖ | — | Tidak relevan selama DB di mesin yang sama. Wajib sebelum DB dipisah |
| **SEC-09** | Kredensial PostgreSQL demo `procur`/`procur`/`procur` | ⏳ **TERBUKA** | `docker-compose.yml` memetakan port hanya ke `127.0.0.1:5432` | Dimitigasi oleh binding lokal. Ganti sebelum deploy |
| **SEC-10** | URL dari web/LLM tidak divalidasi (skema berbahaya, alamat internal) | ✅ **SELESAI** | `security.safe_http_url`: hanya `http`/`https` dengan hostname, maks 2048 karakter; **menolak** `javascript:`, `file:`, `data:`, `ftp:`, loopback, IP privat dan link-local (IPv4 dan IPv6), dan `localhost`. Dipakai di `web_check._save_quotes` dan `evidence.guard_listings`; URL tidak valid disimpan `NULL` (harga tetap). Frontend memfilter lagi sebelum merender tautan (`WebQuotesTable`, `SupplierPanel`) dengan `rel="noopener noreferrer"`. Versi awal terlalu ketat (memblokir Tokopedia/Shopee); sudah ditulis ulang. → `test_security.py` (26 kasus, termasuk 9 kasus alamat internal yang ditambahkan 2 Nov) | **Bukan pertahanan SSRF umum.** Tidak ada resolusi DNS, sehingga bentuk IP alternatif (`http://2130706433/`, `http://127.1/`) dan nama yang menunjuk ke alamat internal (`localtest.me`) lolos (diuji langsung). Risikonya rendah **hari ini** karena backend tidak pernah mengambil URL kutipan (hanya menyimpan dan menampilkannya; satu-satunya panggilan keluar ada di komponen Serper Langflow ke `google.serper.dev`). Menjadi relevan bila suatu hari ada fitur yang mengunduh URL kutipan. Lihat **N-02** |
| **SEC-12** | Kredensial DB default di `config.py` | ✅ **SELESAI** | `DATABASE_URL` dan `JWT_SECRET` (≥ 32 karakter) wajib; aplikasi berhenti saat startup bila kosong. → `test_config_validation.py` (4 tes) | `DEMO_PASSWORD` masih punya nilai bawaan `password123` (N-06) |
| **SEC-13** | Content-Security-Policy belum dipasang | ✅ **SELESAI** | `main.py` mengirim `Content-Security-Policy` pada setiap respons (`default-src 'self'`, font dan style dari Google Fonts, `connect-src` ke Vite dev) | Tidak ada tes otomatis untuk header ini. `style-src` memakai `'unsafe-inline'`. Nilai terikat ke localhost (N-07) |
| **SEC-14** | Skor fuzzy match terlalu longgar | 🟡 **SEBAGIAN** | `matcher.py` mensyaratkan `token_set_ratio ≥ 85` **dan** `token_sort_ratio ≥ 70` | Contoh data E4 (bukan pengukuran) masih menunjukkan `bearing` cocok ke `Bearing 6205 ZZ`. Belum ada ukuran nyata (`KNOWN_ISSUES.md` O-7) |
| **SEC-16/17** | Sesi agent dan file database ikut ter-commit | ✅ **SELESAI** | `.gitignore`: `.env`, `.venv/`, `.bob/`, `.ob1/`, `*.db`, `*.sqlite`, `coverage.json`. Hanya `.env.example` yang dilacak git | — |
| **SEC-18** | Wildcard `LIKE` tidak di-escape pada pencarian | ✅ **SELESAI** | `routers/purchases.py` meng-escape `%`, `_`, dan `\` sebelum membungkus istilah pencarian | `ilike` dipanggil tanpa `escape=` eksplisit, jadi bergantung pada garis miring terbalik sebagai escape bawaan PostgreSQL. Dicoba langsung di SQLite: mencari `%` atau `_` menghasilkan 0 baris (tidak lagi mencocokkan semuanya). Tidak ada tes otomatis |
| **SEC-19** | Tidak ada retry ke Langflow | ✅ **SELESAI** | `langflow_client.run_flow`: 3 percobaan untuk timeout/HTTP error/respons rusak, kegagalan autentikasi (401/403) tidak diulang. → `test_langflow_client.py` | Tiap percobaan sampai 60 detik |
| **LLM10** | Konsumsi berlebihan pada endpoint LLM | ✅ **SELESAI** | `max_length` pada teks parse (10.000) dan quick check (5.000); `slowapi` 10 permintaan per menit per IP pada `/api/requests/parse`, `/api/quick-check`, `/api/request-items/{id}/recheck`, `/api/quotations`; login 5 per menit. → `test_rate_limit.py` (7 tes) | Penghitung berada di memori satu proses (N-08) |

### Pengendalian khusus data dari LLM dan web

| Ancaman | Pengendalian | Lokasi |
|---|---|---|
| Model mengarang URL atau harga | Listing dipakai hanya bila URL-nya ada di hasil Serper untuk `line_no` yang sama, halamannya halaman produk, dan harganya tertulis di judul/snippet | `services/evidence.py` |
| Model salah menghitung | Model tidak menghitung; `pack_qty` dibagi di Python, dibulatkan ke rupiah utuh | `evidence.per_unit_price` |
| JSON model rusak | Kontrak Pydantic, satu kali ulang dengan petunjuk perbaikan, lalu `FlowContractError` | `flows/contracts.py` |
| Prompt injection di dokumen | Pertahanan ada di Python: teks sisipan hanya bisa mengubah string hasil ekstraksi, tidak bisa mengubah band, skor, flag, atau keputusan | fixture `03_injection.txt` di `langflow/fixtures/` |
| Hasil di luar marketplace | Komponen Serper hanya meloloskan `tokopedia.com`, `shopee.co.id`, `blibli.com`, `lazada.co.id` | `langflow/Maker.json` |
| Rahasia di ekspor flow | Skrip pra-commit menolak pola kunci dan `api_key` yang bukan variabel global Langflow | `scripts/check_langflow_secrets.py` |
| Injeksi rumus pada ekspor CSV | Sel berawalan `= + - @ TAB CR` diberi awalan `'` | `decisions._csv_safe` |

---

## Risiko terbuka (hasil tinjauan 2 November)

Butir baru memakai kode **N-xx** agar tidak tertukar dengan ID SEC lama.

| Kode | Tingkat | Risiko | Mengapa penting | Tindakan yang disarankan |
|---|---|---|---|---|
| **N-01** | Sedang | Pesan error Langflow/Serper sampai ke pengguna (SEC-04 sebagian) | Teks exception (bisa memuat URL internal Langflow atau potongan keluaran model dari kegagalan validasi) disimpan di `check_error` dan dikembalikan oleh API | Simpan pesan generik di `check_error` dan catat detailnya di log; samakan perilaku 502 pada `/api/requests/parse` dan `/api/quick-check`. Tambah tes yang memicu kegagalan Langflow |
| **N-02** | Rendah (hari ini) | `safe_http_url` bukan pertahanan SSRF umum | Lihat SEC-10: tanpa resolusi DNS, bentuk IP alternatif lolos | Jangan menambahkan fitur yang mengunduh URL kutipan tanpa menambah resolusi DNS dan pemeriksaan alamat hasil resolusi |
| **N-03** | Sedang (sebelum produksi) | JWT di `localStorage`, tanpa pencabutan | XSS apa pun bisa mencuri token; token yang bocor berlaku sampai 1 jam. Pengguna yang dinonaktifkan langsung ditolak (pengguna dimuat ulang dari DB di setiap permintaan), tetapi tidak ada "logout dari semua perangkat" | Cookie HttpOnly + SameSite, daftar token yang dicabut |
| **N-04** | Sedang (sebelum produksi) | Kekekalan audit log hanya di ORM; hanya keputusan yang dicatat | Admin DB bisa mengubah baris; login, kegagalan login, impor, dan pembuatan request tidak meninggalkan jejak di `audit_log` | Trigger PostgreSQL atau cabut hak `UPDATE/DELETE` untuk peran aplikasi; tambah kejadian login dan impor |
| **N-05** | Sedang | `mask_pii` hanya menutupi satu kolom pada satu respons, dan tidak berlaku sebelum data dikirim ke LLM | Nama supplier, harga, dan nama barang dikirim apa adanya ke penyedia model; panel perbandingan supplier menampilkan nama asli. Peta jalan awal meminta masking sebelum LLM | Putuskan data apa yang boleh keluar; terapkan masking di sisi masuk LLM dan di semua respons yang memuat nama supplier |
| **N-06** | Sedang | `DEMO_PASSWORD` bernilai bawaan `password123`; tidak ada manajemen pengguna | Jika `.env` lupa diisi, ketiga akun memakai sandi yang tertulis di repo | Hapus nilai bawaan (wajibkan diisi), tambah endpoint/CLI untuk membuat dan menonaktifkan pengguna |
| **N-07** | Rendah | CORS, CSP `connect-src`, dan `TrustedHost` di-hardcode ke localhost; CSP memakai `'unsafe-inline'` untuk style; tidak ada tes CSP | Deploy ke host lain akan rusak atau tanpa sengaja dilonggarkan | Jadikan konfigurasi lewat `.env`; tambah tes header CSP |
| **N-08** | Rendah | Pembatas laju hidup di memori satu proses, per IP | Reset saat restart; dengan beberapa worker batasnya terbagi; di belakang proxy semua klien bisa terlihat satu IP | Gunakan penyimpanan bersama (Redis) dan baca IP klien dari header proxy tepercaya |
| **N-09** | Rendah | `GET /api/health` tanpa autentikasi | Mengungkap nama aplikasi dan status Langflow | Biarkan untuk `start.sh`, atau batasi isinya |
| **N-10** | Perlu dicek | Langflow: `LANGFLOW_AUTO_LOGIN` belum dicek; flow di repo belum tentu sama dengan flow yang berjalan | Langflow yang terbuka tanpa login adalah pintu belakang ke API key model dan Serper | Buka `http://localhost:7860` di jendela incognito; pastikan meminta login. Ekspor ulang flow setelah pengaturan model dibakukan (`KNOWN_ISSUES.md` O-3) |
| **N-11** | Sedang | **Fase 3 belum dikerjakan:** `gitleaks`, `pip-audit`, `npm audit`, `bandit`, OWASP ZAP, threat model STRIDE; tidak ada CI (tidak ada `.github/`) | Kerentanan dependensi dan rahasia di riwayat git belum dipindai otomatis. Versi dependensi sudah dipin (`==`) | Jalankan pemindai secara manual lalu pasang di CI. Audit sebelumnya (23 Okt) menemukan tidak ada rahasia di riwayat git; belum diulang |
| SEC-08, SEC-09 | Lihat register | TLS DB, kredensial DB demo | — | Selesaikan sebelum DB dipisah dari mesin aplikasi |

---

## Fase 0: Infrastruktur (selesai, ringkasan)

| Perubahan | Berkas | Dampak |
|---|---|---|
| `start.sh` ditulis ulang: tiap service di grup proses sendiri (`setsid`), cek port bentrok, health check backend/frontend/Langflow, lokasi Langflow lewat `LANGFLOW_DIR` | `start.sh` | Langflow tidak lagi gagal start diam-diam |
| `stop.sh` mematikan seluruh grup proses lalu menampilkan sisa proses | `stop.sh` | Proses anak (Vite, Langflow) tidak menumpuk |
| Langflow dijalankan dengan `--host 127.0.0.1` | `start.sh` | Tidak terbuka ke jaringan |
| Port PostgreSQL dipetakan ke `127.0.0.1:5432` | `docker-compose.yml` | Sebelumnya `0.0.0.0` |
| Tambah `.ob1/`, `.bob/`, `*.db`, `*.sqlite` ke `.gitignore` | `.gitignore` | SEC-16, SEC-17 |

## Fase 1: Hardening kode (selesai, ringkasan)

| # | Commit | Temuan | Perubahan |
|---|---|---|---|
| 1 | `764a466` | SEC-10 | `safe_http_url()` dan penyaringan di frontend (versi awal; ditulis ulang pada 30 Okt agar mengizinkan URL publik) |
| 2 | `b839bac` | SEC-06 | Batas ukuran, magic bytes `.xlsx`, batas 10.000 baris |
| 3 | `ae3f5c3` | SEC-04 (sebagian) | `check_error` generik untuk exception tak terduga |
| 4 | `d757e91` | LLM10 | `max_length` dan rate limit `slowapi` pada endpoint LLM. Catatan: pesan commit menyebut "SEC-01", padahal yang ditutup adalah konsumsi berlebihan; SEC-01 (autentikasi) baru ditutup di Fase 2 |
| 5 | `b8a940f` | SEC-03 | Penjaga `seed --reset` |
| 6 | `f361ec1` | SEC-02 | `TrustedHostMiddleware`, CORS allow-list, header keamanan |
| 7 | `c8f4aa2` | SEC-12 | `DATABASE_URL` wajib |

## Fase 2 (Sektor 1): Autentikasi, peran, audit (selesai)

| Commit | Isi |
|---|---|
| `ed7873f`, `2f007bc`, `751d4c5` | Login JWT, tiga peran, tabel dan UI audit log, navigasi per peran |
| `f6a90df` | M16: setiap rute dijaga, matriks peran, kepemilikan baris, tes "setiap rute 401 tanpa token" |
| `2018f1b` | M19: log keputusan (alasan, tag hasil, potret bukti), halaman Review, ekspor CSV, kekekalan ORM |

---

## Cara memverifikasi

```bash
# Seluruh tes (tidak butuh Langflow atau PostgreSQL)
cd backend && source .venv/bin/activate && pytest

# Tes per topik
pytest tests/test_auth.py tests/test_decisions.py     # SEC-01, audit, Maker-Checker
pytest tests/test_security.py                         # SEC-10
pytest tests/test_middleware.py tests/test_rate_limit.py

# Binding jaringan: semua harus 127.0.0.1
./stop.sh && ./start.sh
ss -ltn | grep -E ':(7860|8000|5173|5432)\b'

# Autentikasi dan host
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/queue                       # 401
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: evil.example.com" http://127.0.0.1:8000/api/health   # 400

# Rahasia di ekspor flow
python scripts/check_langflow_secrets.py
```

Konfigurasi backend dibaca dari `backend/.env`. `DATABASE_URL` dan `JWT_SECRET` wajib diisi. Jangan commit `backend/.env`.

---

## Rujukan

- OWASP ASVS, OWASP API Security Top 10 (2023), OWASP Top 10 for LLM Applications (2025)
- NIST SP 800-218 (SSDF), CIS Benchmark PostgreSQL
- STRIDE (Kohnfelder dan Garg)
