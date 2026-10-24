# Procur.AI — Laporan Temuan Bug & Handover (Known Issues)

Dokumen ini dibuat berdasarkan hasil observasi *End-to-End* (E2E) menggunakan agen AI lokal dan merujuk pada temuan di `AUDIT.md`. 

**Status Aplikasi:** Fitur inti (Organize, Check via History, Check via Web, Queue, Inspector, History Page) sudah berjalan dengan baik. Namun, terdapat beberapa *bug* kritis pada *edge cases* yang harus segera diperbaiki sebelum penjurian/submission.

---

## 🚨 1. Critical Issues (Wajib Diperbaiki)

### 1.1. Link Palsu (Dummy URLs) pada Web Quotes (Ref: AUDIT.md C2)
* **Lokasi:** `backend/app/seed.py` (baris sekitar 591-606)
* **Deskripsi:** Data *seed* untuk barang "Solenoid valve" menggunakan URL palsu (contoh: `https://tokopedia.com/a`, `https://shopee.co.id/b`). Jika juri mengklik link "Offer" di panel Inspector, halaman akan error/not found.
* **Cara Reproduksi:** 
  1. Buka halaman Today.
  2. Klik baris "Solenoid valve 24V DC, 1/2"".
  3. Di panel Inspector (kanan), klik salah satu teks Offer (misal: Tokopedia).
* **Ekspektasi:** Terbuka halaman produk asli.
* **Aktual:** Browser membuka halaman 404/error.
* **Rekomendasi:** Cari 3 link produk asli di Tokopedia/Shopee, masukkan ke `seed.py`, atau ubah teks URL menjadi non-klikabel (plain text) jika tidak ingin repot mencari link asli.

### 1.2. Git Repository Belum Di-push (Ref: AUDIT.md C1)
* **Lokasi:** Folder root proyek.
* **Deskripsi:** Proyek belum di-commit dan di-push ke repositori GitHub. Ini sangat berisiko jika laptop bermasalah, dan tidak ada yang bisa dikumpulkan ke panitia.
* **Rekomendasi:** Segera jalankan `git add .`, `git commit`, dan `git push` ke repository (misal: `github.com/Katonrinantomoproc/procur`).

---

## ⚠️ 2. High Priority Issues (Bug Logika Backend)

### 2.1. Error 500 (Internal Server Error) pada Fitur Quick Check (Ref: AUDIT.md H1)
* **Lokasi:** `backend/app/services/web_check.py` & `backend/app/routers/quick_check.py`
* **Deskripsi:** Jika pengguna mengetik barang yang **belum ada di histori** (baru) dan **belum ada di cache web**, fitur Quick Check akan *crash* (HTTP 500). Ini karena `get_web_quotes` mencoba melakukan `session.refresh()` pada objek `RequestItem` yang belum tersimpan di database.
* **Cara Reproduksi:**
  1. Buka tab Quick check.
  2. Ketik: `Kain sutra putih, 10 yard`.
  3. Klik Check.
* **Ekspektasi:** Muncul kartu hasil "New item" dengan harga web (atau "No price reference found").
* **Aktual:** Layar error 500.
* **Rekomendasi:** Ubah `quick_check` menjadi *plain def* endpoint, dan pastikan `get_web_quotes` tidak memanggil `session.refresh()` pada *shim* (objek sementara) yang belum masuk DB.

### 2.2. Inkonsistensi Referensi Harga Web (Ref: AUDIT.md H2)
* **Lokasi:** `backend/app/services/pricing.py` & `routers/request_items.py`
* **Deskripsi:** `get_web_quotes` mencari cache dengan *fuzzy matching* (kemiripan nama), tetapi perhitungan referensi di inspector menggunakan *exact match* (harus sama persis). Ini menyebabkan referensi harga bisa `null` padahal kuotasi ada di cache.
* **Rekomendasi:** Pastikan fungsi mengembalikan daftar *quote* yang benar-benar dipakai, lalu hitung median dari daftar yang sama. Jangan pernah melakukan query dengan `request_item_id IS NULL` untuk referensi.

---

## 🔍 3. Medium / Low Issues

### 3.1. Error Handling Langflow yang Kurang Ramah (Ref: AUDIT.md M1)
* **Deskripsi:** Jika `LANGFLOW_ORGANIZE_FLOW_ID` kosong atau salah, backend mengembalikan error mentah `405 Method Not Allowed` (atau 404), alih-alih pesan yang mudah dipahami seperti *"Langflow is not configured"*.
* **Rekomendasi:** Gunakan pengecekan konfigurasi yang sama seperti di endpoint `/api/requests/parse` untuk endpoint `/api/quick-check`.

### 3.2. Batas Ukuran File Import Belum Ada (Ref: AUDIT.md M2)
* **Deskripsi:** Fitur upload Excel/CSV saat ini belum membatasi ukuran file (bisa jadi juri mengunggah file 100MB dan membuat server *hang*).
* **Rekomendasi:** Batasi ukuran file maksimal 5MB dan kembalikan error 413 (Payload Too Large) jika melebihi batas.

---

## 📝 Catatan untuk Rekan Tim
- Semua angka (harga, persentase, kalkulasi total) sudah **100% akurat** karena dihitung di Python, bukan oleh AI. Jangan ubah logika matematika di `pricing.py`.
- Untuk pengujian mandiri, pastikan Docker menyala (`docker compose up -d`), backend menyala, Langflow menyala, dan file `backend/.env` sudah terisi `LANGFLOW_API_KEY` serta Flow ID yang valid.
- Gunakan perintah `python -m app.seed --reset --empty-today` untuk mereset ulang data demo sebelum presentasi.