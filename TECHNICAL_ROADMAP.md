# Procur.AI (Tilas) — Technical Roadmap & Action Plan

**Sumber:** Feedback Mentor Hackathon IBM SkillsBuild (Semi-Final)
**Tujuan:** Menerjemahkan kritik dan saran mentor menjadi fitur teknis yang terukur, aman, dan siap untuk Final.
**Branch Utama:** `main` (Setelah merge dari `security`)

---

## 🚨 1. Sektor Keamanan & Otorisasi (Security & Auth)
*Kritik Mentor:* "Lengkapi autentikasi dan pemeriksaan hak akses/ownership pada endpoint API."

| Fitur / Tugas | Deskripsi Teknis | Status |
| :--- | :--- | :--- |
| **Autentikasi API (JWT)** | Tambahkan endpoint `POST /api/auth/login`. Gunakan JWT (JSON Web Token) untuk mengamankan semua endpoint API. Hanya user terautentikasi yang bisa mengakses data. | ⏳ *Todo* |
| **Role-Based Access Control (RBAC)** | Bedakan hak akses: `purchasing` (Maker) hanya bisa submit request. `owner` (Checker) yang boleh menekan tombol Approve/Return. | ⏳ *Todo* |
| **Audit Log (Terlacak)** | Buat tabel `audit_logs` di database. Catat: `user_id`, `action` (approve/return), `timestamp`, dan `notes`. Setiap aksi approve/return wajib menyimpan log ini. | ⏳ *Todo* |

---

## ⚖️ 2. Sektor Backend & Business Logic (Python)
*Kritik Mentor:* "Status harga dan skor vendor masih dihitung LLM. Pindahkan ke kode Python. Masking PII belum ditemukan."

| Fitur / Tugas | Deskripsi Teknis | Status |
| :--- | :--- | :--- |
| **Pindahkan Logika Skor ke Python** | Ubah perhitungan status harga (WAJAR/PERHATIAN/TIDAK WAJAR) dan skor vendor (0-100) agar dihitung murni menggunakan *if-else* di `pricing.py` atau `checker.py`, bukan dari respons JSON LLM. | ⏳ *Todo* |
| **PII Masking (FR-14)** | Buat fungsi `mask_pii(text)` di `security.py` untuk menyamarkan data sensitif (NPWP, No. Rekening, Nama Vendor) sebelum dikirim ke LLM atau ditampilkan ke Frontend. | ⏳ *Todo* |
| **Risk Score (0-100)** | Buat algoritma deterministik di Python untuk menghitung risiko (misal: telat bayar +20 poin, split PO +30 poin, supplier baru +10 poin). | ⏳ *Todo* |

---

## 🧪 3. Sektor Quality Assurance (QA) & Evaluasi AI
*Kritik Mentor:* "Titik lemah sebenarnya adalah akurasi ekstraksi LLM belum diukur. Butuh dataset ground truth."

| Fitur / Tugas | Deskripsi Teknis | Status |
| :--- | :--- | :--- |
| **Dataset Ground Truth** | Kumpulkan 20-30 set dokumen (PO, GR, Invoice, Faktur) yang memiliki nilai asli (ground truth) per field-nya. | ⏳ *Todo* |
| **Script Pengukuran Akurasi** | Buat script Python (`test_accuracy.py`) untuk membandingkan ekstraksi LLM dengan ground truth. Hitung *Field-level Accuracy* dan *Exact Match*. | ⏳ *Todo* |
| **Error Propagation Test** | Uji seberapa fatal error ekstraksi (misal: LLM salah baca 1.000 jadi 10.000) mempengaruhi keputusan audit akhir (Flagged/Checked). | ⏳ *Todo* |
| **Evaluasi Serper API (MAPE)** | Bandingkan hasil harga Serper API dengan harga manual untuk 15 item. Hitung MAPE dan persentase Serper mengembalikan hasil kosong. | ⏳ *Todo* |
| **Sinkronisasi Test** | Perbaiki `README.md` yang menyebutkan 72 tes (padahal aslinya 86+ tes). | ⏳ *Todo* |

---

## 🖥️ 4. Sektor Frontend / UI (Dashboard)
*Kritik Mentor:* "Prioritaskan dashboard untuk meninjau temuan dan merekam keputusan reviewer."

| Fitur / Tugas | Deskripsi Teknis | Status |
| :--- | :--- | :--- |
| **Halaman Review / Audit** | Tampilan UI khusus untuk Checker melihat daftar barang/dokumen yang berstatus *Flagged* (merah) beserta alasannya. | ⏳ *Todo* |
| **Tombol Aksi & Catatan** | Di UI tersebut, Checker bisa menekan *Approve* / *Return* dan mengetik catatan alasan penolakan (yang nanti masuk ke Audit Log). | ⏳ *Todo* |

---

## 📝 Catatan Progress Saat Ini (Branch: `security`)
Beberapa hal yang **sudah diselesaikan** sebelum Final:
- [x] Integrasi Google Serper API (menggantikan Web Search bawaan).
- [x] Perbaikan celah SSRF di `security.py` (URL publik diizinkan, IP privat diblokir).
- [x] Perbaikan Error 500 pada Quick Check (H1).
- [x] Sinkronisasi cache logika Web Check (H2).
- [x] URL Dummy di seed diganti (C2).
- [x] Penambahan Retry Langflow (SEC-19), Escape Wildcard (SEC-18), dan Strict Matcher (M4).