# Procur.AI (Tilas) — Rencana Video Demo & Matriks RBAC

Dokumen ini adalah panduan lengkap untuk merekam video demo Hackathon (durasi 3-5 menit). Bagian pertama menjelaskan logika bisnis dan hak akses (RBAC), bagian kedua adalah naskah langkah demi langkah.

---

## Bagian 1: Matriks RBAC & Skema Bisnis (Maker-Checker)

Aplikasi ini menggunakan model **Maker-Checker** dengan 3 peran (Role) utama. Setiap peran memiliki batasan akses yang ketat (Enforced via Backend API & Frontend UI).

### 1.1 Matriks Hak Akses (Role-Based Access Control)

| Fitur / Halaman | Purchasing (Maker) | Owner (Checker) | Finance (Pendukung) |
| :--- | :---: | :---: | :---: |
| **Landing Page** | ✅ (Lihat) | ✅ (Lihat) | ✅ (Lihat) |
| **Add Requests** (Buat Request) | ✅ (Bisa) | ✅ (Bisa) | ❌ (Disembunyikan) |
| **Quick Check** (Dry-run) | ✅ (Bisa) | ✅ (Bisa) | ✅ (Bisa) |
| **Today (Queue)** | ✅ (Lihat) | ✅ (Lihat) | ✅ (Lihat) |
| **Tombol Approve / Return** | ❌ (Waiting for approval) | ✅ (Bisa) | ❌ (Waiting for approval) |
| **History (Purchases/Requests)**| ✅ (Lihat) | ✅ (Lihat) | ✅ (Lihat) |
| **Audit Log** (Jejak Rekam) | ❌ (Tidak muncul) | ✅ (Bisa) | ✅ (Bisa) |
| **Import Excel** | ✅ (Bisa) | ✅ (Bisa) | ❌ (Disembunyikan) |

### 1.2 Skema Bisnis: Kondisi Request & Validasi
Sistem dirancang untuk menangani input yang tidak lengkap (seperti pesan WhatsApp).

| Kondisi Input | Aksi Sistem (Backend Python) | Status / Flag yang Muncul |
| :--- | :--- | :--- |
| **Ada Harga & Ada Supplier** | Hitung selisih harga (`diff_pct`). Bandingkan dengan histori/web. | `Checked` (jika wajar), `Flagged` (jika mahal/new supplier). |
| **Ada Harga, Tanpa Supplier** | Hitung selisih harga. Supplier kosong. | `Checked` / `Flagged` (tanpa flag supplier). |
| **Tanpa Harga, Ada Supplier** | Cari harga via Web Check (Serper). Bandingkan. | `New Item` / `Flagged`. |
| **Tanpa Harga, Tanpa Supplier** | Cari harga via Web Check. | `New Item`. |
| **Supplier Baru (Belum di DB)** | Picu flag `NEW_SUPPLIER`. Tambah poin Risk Score. | `Flagged` (Risk Score bertambah +25). |
| **Harga > 15% Referensi** | Picu flag `PRICE_ABOVE_REF`. | `Flagged` (Risk Score bertambah +30). |

---

## Bagian 2: Draft Naskah Video Demo (Durasi ~4 Menit)

**Persiapan Sebelum Rekam:**
1. Jalankan `./start.sh` (Pastikan DB, Backend, Langflow, Frontend menyala).
2. Reset DB: `python -m app.seed --reset --empty-today`.
3. Buka browser di halaman Landing Page (`http://localhost:5173`). Jangan login dulu.

### 🎬 Scene 1: Pembukaan & Masalah (0:00 - 0:30)
**Tampilan:** Landing Page Procur.AI.
**Narasi:**
> *"Halo, kami dari tim Procur.AI. Perusahaan menengah sering mengalami kebocoran anggaran karena pengadaan via WhatsApp tanpa pencatatan yang rapi. Kami memecahkan ini dengan **Tilas**: Agen AI Maker-Checker. AI mengurus ekstraksi bahasa, Python menghitung angka, dan keputusan akhir di tangan manusia."*

### 🎬 Scene 2: Alur Maker / Purchasing (0:30 - 1:45)
**Aksi:**
1. Klik **Masuk** -> Login sebagai `purchasing` / `password123`.
2. Tunjukkan header: *"Logged in as purchasing"*.
3. Klik **Add Requests**. Paste teks:
   > *"Gudang minta oli hidrolik 46 20L 4 drum, harga 1,45jt/drum dari CV Sinar Pelumas. Sama beliin helm proyek putih 5 pcs."*
4. Klik **Organize**. Tunjukkan AI (Langflow) mengekstrak 2 barang.
5. Klik **Save and check**.
6. Klik baris **Hydraulic Oil**.
**Narasi:**
> *"Sebagai staf purchasing (Maker), saya memasukkan request. AI langsung mengekstrak teks berantakan ini. Perhatikan panel Inspector: Sistem mendeteksi harga oli ini **TIDAK WAJAR** (+29.5% dari histori). Ada **Risk Score 70/100**. Nama supplier juga sudah disamarkan (PII Masking) menjadi CV S**** P******. Sebagai Maker, saya tidak bisa menyetujui ini. Tombol Approve disembunyikan."*

### 🎬 Scene 3: Alur Checker / Owner (1:45 - 3:00)
**Aksi:**
1. Klik **Logout** -> Login sebagai `owner` / `password123`.
2. Buka baris **Hydraulic Oil** yang berstatus Flagged.
3. Tunjukkan tombol **Approve** dan **Return to requester** sekarang muncul.
4. (Opsional) Buka baris **Helm Proyek Putih**. Klik, dan tunjukkan bahwa sistem memanggil **Web Check** (Tokopedia) karena tidak ada histori.
5. Kembali ke **Hydraulic Oil**, klik **Approve**.
**Narasi:**
> *"Sekarang saya login sebagai Owner (Checker). Sesuai prinsip RBAC, hanya saya yang bisa mengambil keputusan. Saya melihat rincian flag-nya. Untuk helm tadi, sistem otomatis mencari harga ke Tokopedia via Serper API karena barang baru. Untuk oli ini, saya putuskan untuk Approve."*

### 🎬 Scene 4: Audit Log & Finance (3:00 - 3:45)
**Aksi:**
1. Klik menu **Audit Log** di navigasi atas (khusus Owner & Finance).
2. Tunjukkan tabel jejak rekam (Waktu, Item, Aksi, User).
3. Klik **Logout** -> Login sebagai `finance` / `password123`.
4. Tunjukkan halaman awal langsung mengarah ke **History**, dan tombol Add Requests hilang.
**Narasi:**
> *"Setiap keputusan tercatat secara digital di **Audit Log**. Finance bisa melihat riwayat ini untuk memeriksa tagihan. Perhatikan, saat login sebagai Finance, tombol Add Requests disembunyikan karena mereka hanya bertugas memeriksa, bukan membuat request."*

### 🎬 Scene 5: QA & Penutup (3:45 - 4:00)
**Tampilan:** Tampilkan terminal yang menunjukkan hasil `eval_llm.py` (100%) dan `qa_report.json`.
**Narasi:**
> *"Terakhir, kami tidak hanya membangun, tapi mengukur. QA Pipeline kami menunjukkan akurasi ekstraksi LLM mencapai **100%** (semantic match), dengan Coverage Rate Web Check yang transparan. Procur.AI: Cegah kebocoran anggaran, selamatkan margin perusahaan. Terima kasih."*
