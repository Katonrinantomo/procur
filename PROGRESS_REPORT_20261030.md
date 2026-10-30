# Progress Report — 30 Oktober 2026

**Fokus Hari Ini:** Integrasi Google Serper API, Perbaikan Validasi Keamanan URL (SSRF), Penyempurnaan UI Web Check, dan Perbaikan Bug Quick Check.
**Branch:** `security`
**Status:** ✅ Selesai (Fitur Web Check berjalan 100% End-to-End dengan E-commerce Lokal, 232 Tests Passed)

---

## Ringkasan Eksekusi
Hari ini, fokus utama adalah menyelesaikan masalah pada *Web Check Flow* dan *Quick Check* yang sebelumnya sering mengembalikan nilai kosong (`[]`), URL tidak bisa diklik, atau *crash* (HTTP 500). 

Semua perubahan ini berhasil menyelesaikan temuan **AUDIT H1, H2, M1**, dan **SEC-10**.

---

## Detail Pekerjaan (Berdasarkan Git Status)

### 1. `backend/app/services/web_check.py` & `backend/app/routers/quick_check.py` (Bug Fix H1 & H2)
*   **Masalah:** Quick Check error 500 saat mencari barang baru. Logika cache web *fuzzy match* dan *exact match* tidak sinkron.
*   **Solusi:** Endpoint `quick_check` diubah menjadi plain `def`. Menghapus pemanggilan `session.refresh()` pada objek yang belum tersimpan. Menyinkronkan median harga dan tabel quotes berdasarkan list yang sama.
*   **Dampak:** Fitur Quick Check tidak akan *crash* lagi untuk barang yang belum ada di database.

### 2. `backend/app/services/web_check.py` (Modifikasi Query)
*   **Masalah:** Query `"harga <nama barang>"` terlalu umum dan membuat Google Serper API mengembalikan hasil dari Amazon/eBay (USD).
*   **Solusi:** Memodifikasi fungsi `_flow_input` untuk menyisipkan operator `site:` secara dinamis.
*   **Dampak:** Backend memaksa Google Serper API hanya mencari di e-commerce lokal Indonesia (Tokopedia, Shopee, Blibli, Lazada).

### 3. `backend/app/security.py` (Perbaikan SSRF)
*   **Masalah:** Fungsi `safe_http_url` memblokir URL valid dari Tokopedia/Shopee.
*   **Solusi:** Menulis ulang fungsi `safe_http_url` menggunakan `urllib.parse` dan `ipaddress` untuk memblokir IP privat/loopback, namun meloloskan URL publik.
*   **Dampak:** Celah keamanan SSRF (SEC-10) tertutup, URL produk e-commerce berhasil disimpan.

### 4. `frontend/src/components/WebQuotesTable.tsx` (Perbaikan UI)
*   **Masalah:** URL dari backend tersimpan tetapi tidak bisa diklik di UI.
*   **Solusi:** Menambahkan tag `<a>` dengan atribut `target="_blank" rel="noopener noreferrer"` dan styling biru/underline.
*   **Dampak:** Tautan *Offer* bisa diklik menuju halaman produk.

---

## Uji Coba & Hasil
*   **Pytest:** 232 Passed, 0 Failed.
*   **Skenario Messy Input:** Berhasil mengekstrak teks WhatsApp, mencari harga di Tokopedia via Serper API, dan mendeteksi *Flagged* (Harga mahal & Supplier baru) secara akurat.

---

## Sinkronisasi dengan Dokumen Sebelumnya
*   **SEC-10 (Unvalidated URL)** ➡️ **Resolved**.
*   **AUDIT H1, H2, M1** ➡️ **Resolved**.
*   **SEC-05 (Quick Check)** ➡️ **Resolved**.

---

## Langkah Selanjutnya (Next Steps)
1.  **Handoff:** Berikan informasi ke tim bahwa *Web Check Flow* dan *Quick Check* sudah stabil dan siap untuk presentasi Hackathon.
2.  **Fase 2 (Security):** Autentikasi (SEC-01) dan Audit Log masih belum dikerjakan dan menjadi PR jangka panjang.

---

## Sektor 2 (Backend & Business Logic) - SELESAI
- **Implementasi Risk Score (0-100):** Membuat fungsi `calculate_risk_score` di `flags.py` yang menghitung risiko murni menggunakan Python (berdasarkan bobot flag: PRICE_ABOVE_REF +30, STOCK_COVER_HIGH +20, NEW_SUPPLIER +10, dan tambahan poin dari besaran `diff_pct`). Tidak ada perhitungan dari LLM.
- **Migrasi Database:** Menambahkan kolom `risk_score` (Integer) pada tabel `request_items` via Alembic.
- **Update Check Engine & Seed:** Memastikan fungsi `_do_check` di `checker.py` dan proses seeding menyimpan nilai `risk_score` ke database.
- **Update UI Inspector:** Menampilkan *badge* "Risk Score: X/100" di panel Inspector Frontend, dengan warna dinamis (Merah >50, Kuning 20-49, Hijau <20).
- **Hasil Uji:** Seed berhasil, dan query database menunjukkan skor yang akurat (misal: Work gloves = 37, V-belt = 40).
