# Procur.AI: Masalah Diketahui (Known Issues) & Handover

Diperbarui: **2 November 2026** · Kode: `main` @ `a81bc47` · Menggantikan versi 30 Oktober, yang menyatakan "tidak ada isu High" dan "semua angka 100% akurat".

Dokumen ini hanya memuat masalah **fungsional dan kualitas**. Masalah keamanan ada di [`SECURITY_PROGRESS.md`](SECURITY_PROGRESS.md). Dokumen yang usang: [`DOCS_AUDIT.md`](DOCS_AUDIT.md).

## Status saat ini

Fitur inti berjalan: antrean Today, Add requests, Quick check, History, Import Excel/CSV, penawaran vendor, Review, dan Audit Log. Hasil uji otomatis: **514 lulus, 1 dilewati dari 515** (yang dilewati adalah tes langsung ke Langflow). Namun **kualitas keluaran AI belum memenuhi syarat demo tanpa pengawasan**: nama barang hasil Organize hanya 20% cocok dengan kunci jawaban (O-1).

| Tingkat | Terbuka | Selesai |
|---|---:|---:|
| 🔴 Tinggi | **1** (O-1) | 3 |
| 🟠 Sedang | **5** (O-2 sampai O-6) | 3 |
| 🟡 Rendah | **3** (O-7 sampai O-9) | 3 |

---

## 🔴 TERBUKA: Tinggi

### O-1. Nama barang hasil Organize hanya 20% akurat (model menerjemahkan ke Bahasa Inggris)

**Status: TERBUKA. Belum diperbaiki.** Pemilik: orang yang memegang `langflow/Organize.json` (perubahan ada di Langflow, bukan di kode backend).

**Yang terukur** (suite E1, 31 Oktober 2026, commit `2018f1b`; sumber: `backend/eval/results.md`; 3 pesan, **5 baris** kunci jawaban):

| Kolom | Benar / Baris | Akurasi |
|---|---:|---:|
| **`item` (nama barang)** | **1 / 5** | **20,0%** |
| `qty` | 5 / 5 | 100,0% |
| `unit` | 5 / 5 | 100,0% |
| `price` | 5 / 5 | 100,0% |
| `supplier` | 5 / 5 | 100,0% |
| `department` | 5 / 5 | 100,0% |
| Baris terlewat / dikarang | 0 / 0 | n/a |

**Baris yang gagal:**

| Teks pesan | Kunci jawaban | Keluaran model |
|---|---|---|
| `... oli 4 drum ...` | `oli` | `Lubricating oil` ✗ |
| `... bearing SKF 6205 ...` | `bearing SKF 6205` | `Bearing SKF 6205` ✓ (satu-satunya) |
| `... lakban bening 2 inch ...` | `lakban bening 2 inch` | `Clear packing tape 2 inch` ✗ |
| `... sarung tangan katun ...` | `sarung tangan katun` | `Cotton gloves` ✗ |
| `... masker kain ...` | `masker kain` | `Cloth face mask` ✗ |

Keempat kegagalan adalah cacat yang sama: **nama barang diterjemahkan ke Bahasa Inggris.** Angka, satuan, supplier, dan departemen terbaca benar.

**Dampak.**
- Pengguna melihat nama yang berbeda dari yang ditulisnya; pencocokan katalog (`rapidfuzz`, ambang 85) bisa salah atau meleset.
- E1b: **1 dari 5 baris berubah flag-nya** karena salah baca (`lakban bening 2 inch` mendapat `QTY_UNUSUAL` palsu setelah menjadi "Clear packing tape 2 inch"). Mengapa terjemahan mengubah pencocokan belum diselidiki.
- Python menghitung dengan tepat, tetapi **dari masukan yang salah baca**. Karena itu klaim "semua angka 100% akurat" yang ada di versi lama dokumen ini dicabut.

**Penyebab.**
- Prompt di `Organize.json` **sudah melarang** terjemahan ("KEEP THE ITEM NAME IN THE ORIGINAL LANGUAGE (Indonesian) ... Do NOT translate"). Model mengabaikannya, jadi mengubah kalimat itu saja kemungkinan tidak cukup.
- `Organize.json` diekspor dengan model `OpenAI Compatible: langflow` (gateway lokal), bukan `claude-haiku-5-5` seperti yang dimaksud README. Temperatur 0,1.
- Contoh tunggal di prompt memiliki keluaran yang diperluas (`Oli hidrolik ISO VG 46, 20L`), tanpa contoh nama pendek yang tetap pendek.
- **Proyek tidak konsisten soal bahasa:** nama utama katalog seed memakai Bahasa Inggris (`Hydraulic oil ISO VG 46, 20L`, `Bearing 6205 ZZ`) dengan sebagian alias Indonesia, prompt meminta Bahasa Indonesia, dan pesan demo di README memakai Bahasa Inggris. Metrik E1 bisa jadi menghukum keluaran yang bisa dibenarkan; ini keputusan produk yang harus diambil.

**Perbaikan yang disarankan** (berurutan):
1. Pilih satu konvensi bahasa; selaraskan alias katalog, prompt, dan kunci jawaban (`name_accept` bila Bahasa Inggris dapat diterima).
2. Pada setiap node *Language Model* di `Organize.json`: pilih model yang dimaksud, temperatur 0.
3. Tambahkan 2–3 contoh few-shot di prompt dengan nama yang tetap pendek dan tidak diterjemahkan (`lakban bening 2 inch` tetap `lakban bening 2 inch`).
4. Ekspor ulang flow, jalankan `python scripts/check_langflow_secrets.py`.
5. Perbanyak data di `backend/eval/data/e1/` sampai 30 pesan, lalu ukur ulang: `python -m eval.run --suite E1`.

**Kriteria selesai.** Akurasi `item` **≥ 95%** pada ≥ 30 pesan, kolom lain tetap ≥ 95%, dan `eval/results.md` hasil run baru di-commit (hash flow di berkas harus cocok dengan flow yang diekspor). *Angka 95% adalah usulan target, bukan ambang yang sudah ada di proyek.*

**Batasan angka 20%:** hanya 5 baris (indikasi kuat, bukan laju yang presisi); angka ini nilai tercatat 31 Oktober, belum diukur ulang karena Langflow tidak tersedia saat dokumen ini ditulis. Skrip lama yang melaporkan "100%" (`backend/qa/eval_llm.py`, commit `6be9dc2`, sudah dihapus) memakai pencocokan *semantik*; metodenya berbeda, jadi jangan dibandingkan langsung.

**Sementara belum diperbaiki:** minta pengguna memeriksa kolom nama di pratinjau *Add requests* sebelum menyimpan. Detail: `DOCS_AUDIT.md` bagian 1.

---

## 🟠 TERBUKA: Sedang

### O-2. `Maker.json` diperbaiki di repo, tetapi flow yang sudah diimpor perlu diimpor ulang
- **Masalah.** Backend membaca tiga output Chat Output (`extract_json`, `maker_json`, `serper_raw`). Ekspor lama hanya punya dua, sehingga setiap web check dan pengecekan penawaran berakhir `pending` dengan pesan `Flow output 'extract_json' not found`.
- **Status.** Output `extract_json` sudah ditambahkan ke `langflow/Maker.json` (2 November) dan dijaga oleh `backend/tests/test_langflow_exports.py`. **File yang diubah belum dibuka di Langflow sungguhan**, jadi penerimaan impor belum terbukti.
- **Tindakan.** Impor ulang `Maker.json`, salin Flow ID baru ke `LANGFLOW_MAKER_FLOW_ID`, lalu jalankan `python -m app.flowcheck`. Langkah manual bila perlu: `langflow/maker_agent_prompts.md`.

### O-3. Model dan temperatur tidak seragam antar flow
`Maker.json`: Anthropic `claude-haiku-5-5`. `Organize.json` dan `Web Check.json`: gateway OpenAI-compatible. Temperatur 0,1 di semua flow (rekomendasi: 0). Hasil evaluasi tidak bisa direproduksi oleh orang yang mengikuti README. Bakukan bersama perbaikan O-1, ekspor ulang, dan perbarui README bila perlu.

### O-4. Akurasi harga web belum terukur
Suite E3 (MAPE harga web) **dilewati**: `eval/data/e3_prices.csv` berisi 10 nama barang tetapi tidak satu pun punya harga manual, tanggal, dan URL. **Tidak ada nilai MAPE**, dan tidak boleh dikutip. Data lain juga masih contoh: E2 (8 baris) dan E4 (8 nama) berlabel "EXAMPLE DATA, not a measurement". Isi data sesuai `backend/eval/data/README.md`, lalu `python -m eval.run --suite E3`.

### O-5. Pesan error Langflow/Serper sampai ke pengguna
Kegagalan tak terduga sudah disanitasi, tetapi jalur kegagalan Langflow tidak: `check_error` berisi `web_check failed: <teks exception>` dan `/api/requests/parse` mengembalikan `str(exc)`. Terverifikasi: `web_check failed: Langflow call failed after 3 attempts: ConnectError(...)`. Ini juga butir keamanan (N-01 di `SECURITY_PROGRESS.md`). Perbaikan: simpan pesan generik, catat detail di log, tambah tes.

### O-6. Kutipan solenoid di seed adalah data demo, tetapi UI menyebutnya "captured"
Tiga kutipan *Solenoid valve* (Rp 398.000 / 425.000 / 465.000) ditulis tangan di `seed.py` dengan nama marketplace asli tetapi **tanpa URL**; UI menampilkan "Quotes captured 11 Oct 2026". Tautan palsu sudah dihapus (lihat Selesai), tetapi angkanya bukan hasil pencarian nyata. Beri label "contoh/demo" di UI, atau ganti dengan tiga listing nyata beserta URL-nya.

---

## 🟡 TERBUKA: Rendah

### O-7. Pencocokan nama pendek masih bisa salah (dimitigasi sebagian)
`matcher.py` kini mensyaratkan `token_set_ratio ≥ 85` dan `token_sort_ratio ≥ 70`. Pada data contoh E4, `bearing` (ambigu antara dua tipe) masih cocok ke `Bearing 6205 ZZ` (1 dari 8, 12,5%). Itu bukan pengukuran (data contoh), tetapi menunjukkan celahnya. Selesaikan dengan data E4 sungguhan (40 nama).

### O-8. `dry_check_item` adalah salinan `_do_check`
Perubahan di salah satu bisa menyimpang diam-diam dari yang lain (AUDIT.md M5). Ekstrak langkah bersama ke satu fungsi.

### O-9. Celah tes pada perbaikan yang sudah ada
Header `Content-Security-Policy` dan escape wildcard `LIKE` pada pencarian pembelian berfungsi (diperiksa langsung) tetapi tidak punya tes otomatis. `ARCHITECTURE.md` §9 dan `DOCS_AUDIT.md` mencatat butir dokumentasi lain.

---

## ✅ SELESAI (dengan bukti)

| Ref | Masalah | Status | Bukti |
|---|---|---|---|
| **SEC-01** | Tidak ada autentikasi dan otorisasi | ✅ **RESOLVED** | Login JWT, tiga peran, setiap rute dijaga. `routers/auth.py`; `tests/test_auth.py` (28 tes). Batas: token di `localStorage` (N-03) |
| **SEC-10** | Validasi URL / SSRF | ✅ **RESOLVED** | `security.safe_http_url`: hanya http(s), menolak loopback/privat/link-local/`localhost`, mengizinkan Tokopedia/Shopee; `tests/test_security.py` (26 kasus). Batas: bukan pertahanan SSRF umum, tanpa resolusi DNS (N-02) |
| **Audit logging** | Keputusan tidak tercatat | ✅ **RESOLVED** | Tabel `audit_log` append-only (ORM) dengan potret bukti; `services/decisions.py`; `tests/test_decisions.py` (26 tes). Batas: hanya keputusan, dan kekekalan hanya di ORM (N-04) |
| 1.1 / C2 | Tautan kutipan web palsu | ✅ (dengan catatan O-6) | Placeholder diganti `None`; hasil web melalui Serper dan `safe_http_url` |
| 1.2 / C1 | Repositori belum di-push | ✅ | `origin/main` = `HEAD` (`a81bc47`); branch `security` sudah digabung ke `main` |
| 2.1 / H1 / SEC-05 | Quick Check error 500 untuk barang baru | ✅ | `quick_check` menjadi `def` biasa; `tests/test_web_price_path.py` |
| 2.2 / H2 | Referensi harga web tidak konsisten (fuzzy vs exact) | ✅ | `get_web_quotes` mengembalikan kutipan yang dipakai; median dan tabel kutipan dihitung dari daftar yang sama |
| 3.1 / M1 | Pesan error Langflow tidak ramah | ✅ | Quick check memakai pemeriksaan konfigurasi yang sama dengan Parse |
| 3.2 / M2 / SEC-06 | Batas ukuran dan validasi berkas impor | ✅ | 5 MB (impor) / 10 MB (penawaran), magic bytes `.xlsx` dan `.pdf`, 10.000 baris; `tests/test_import.py`, `test_quotations.py`. *(Versi lama dokumen ini menyebut "magic bytes belum diimplementasikan"; itu sudah tidak benar.)* |
| 3.3 / SEC-13 | Content-Security-Policy | ✅ | Header di `main.py`. Batas: tanpa tes, `'unsafe-inline'` untuk style (N-07) |
| M3 | Error DB saat pengecekan menggagalkan seluruh request | ✅ | Setiap baris dicek dalam savepoint; gagal berarti `pending` |
| L2 | Traceback tersimpan dan terkirim ke klien | 🟡 | Selesai untuk exception tak terduga; **belum** untuk jalur Langflow (O-5) |

---

## Catatan untuk rekan tim

- **Yang dijamin Python:** harga referensi, persentase, flag, risk score, band, rekomendasi, dan skor vendor dihitung di Python, bukan oleh model. **Yang tidak dijamin:** apa yang dibaca model dari teks (O-1) dan listing web yang dicocokkan (dibatasi oleh pengecekan bukti, tetapi akurasinya belum terukur, O-4).
- Pencarian Serper dibatasi ke Tokopedia, Shopee, Blibli, dan Lazada oleh komponen *Serper Multi Search* di `Maker.json` (bukan lagi oleh backend).
- Untuk uji mandiri: `./start.sh`, lalu `python -m app.seed --reset --empty-today`. Akun: `purchasing`, `owner`, `finance` (sandi = `DEMO_PASSWORD`).
- Sebelum merekam demo: ikuti daftar persiapan di `DEMO_VIDEO_PLAN.md`, terutama impor ulang `Maker.json` dan `python -m app.flowcheck`.
