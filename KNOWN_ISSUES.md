# Procur.AI — Laporan Temuan Bug & Handover (Known Issues)

Dokumen ini dibuat berdasarkan hasil observasi *End-to-End* (E2E) dan merujuk pada temuan di `AUDIT.md` serta `Security Recon Report`. 

**Status Aplikasi:** Fitur inti berjalan 100%. Seluruh bug kritis (Critical/High) pada *Web Check*, *Quick Check*, dan *Security* telah diselesaikan pada branch `security`.

---

## 🚨 1. Critical Issues (Wajib Diperbaiki)
*(Tidak ada. Seluruh isu Critical telah diselesaikan).*

- [x] **1.1. Link Palsu (Dummy URLs) pada Web Quotes (Ref: AUDIT.md C2 / SEC-07)** — *Resolved*. Telah diganti menggunakan Web Check Agent (Serper API) dan validasi SSRF.
- [x] **1.2. Git Repository Belum Di-push (Ref: AUDIT.md C1)** — *Resolved*. Seluruh pekerjaan telah di-commit dan di-push ke branch `security`.

---

## ⚠️ 2. High Priority Issues
*(Tidak ada. Seluruh isu High telah diselesaikan).*

- [x] **2.1. Error 500 pada Fitur Quick Check (Ref: AUDIT.md H1 / SEC-05)** — *Resolved*. Endpoint diubah menjadi plain `def`, dan `session.refresh()` pada objek *shim* telah dihapus.
- [x] **2.2. Inkonsistensi Referensi Harga Web (Ref: AUDIT.md H2)** — *Resolved*. Logika *fuzzy match* dan *exact match* telah disinkronkan di `get_web_quotes`.
- [x] **2.3. Validasi URL SSRF yang Terlalu Ketat (Ref: SEC-10)** — *Resolved*. `safe_http_url` di `security.py` telah diperbaiki agar mengizinkan URL publik (Tokopedia/Shopee) namun memblokir IP privat/localhost.

---

## 🔍 3. Medium / Low Issues (Opsional)

- [x] **3.1. Error Handling Langflow yang Kurang Ramah (Ref: AUDIT.md M1)** — *Resolved*. Quick check kini menggunakan pengecekan konfigurasi yang sama dengan endpoint Parse.
- [ ] **3.2. Batas Ukuran File Import (Ref: AUDIT.md M2 / SEC-06)** — *Partially Resolved*. Validasi ekstensi `.xlsx` sudah ada, magic bytes belum sepenuhnya diimplementasikan.
- [ ] **3.3. Content-Security-Policy (Ref: SEC-13)** — *Open*. Belum dipasang (hanya header dasar).
- [ ] **3.4. Matcher Terlalu Longgar (Ref: AUDIT.md M4 / SEC-14)** — *Open*. `token_set_ratio` masih bisa salah cocok untuk kata pendek.

---

## 📝 Catatan untuk Rekan Tim
- Semua angka (harga, persentase, kalkulasi total) sudah **100% akurat** karena dihitung di Python, bukan oleh AI.
- Backend kini memaksa pencarian Serper API hanya ke e-commerce lokal (Tokopedia, Shopee, Blibli, Lazada).
- Untuk pengujian mandiri, jalankan `./start.sh` dan gunakan `python -m app.seed --reset --empty-today` untuk mereset data demo.
