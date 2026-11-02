# Procur.AI (Tilas) — Rencana Video Demo & Matriks RBAC

Panduan merekam video demo Hackathon (durasi 4–5 menit). Bagian 1 menjelaskan hak akses dan logika bisnis **sesuai kode saat ini**. Bagian 2 adalah naskah per adegan. Bagian 3 berisi daftar klaim yang boleh dan tidak boleh diucapkan di video.

> **Revisi 2 November 2026.** Versi sebelumnya mengklaim akurasi ekstraksi LLM "100%" dan salah menulis hak akses Quick Check dan Import. Keduanya sudah dikoreksi di sini. Sumber kebenaran: kode di `backend/app/routers/`, `backend/eval/results.md`, dan [`ARCHITECTURE.md`](ARCHITECTURE.md). Status dokumen yang usang: [`DOCS_AUDIT.md`](DOCS_AUDIT.md).

---

## Bagian 1: Matriks RBAC & Skema Bisnis (Maker-Checker)

Tiga peran, dipaksakan oleh **Backend API** (UI hanya menyembunyikan tombol; permintaan yang dibuat manual tetap ditolak dengan 403).

| Peran | Posisi Maker-Checker | Akun demo (password = `DEMO_PASSWORD`, default `password123`) | Halaman awal setelah login |
| :--- | :--- | :--- | :--- |
| `purchasing` | **Maker** — membuat dan mengecek request | `purchasing` | Today |
| `owner` | **Checker** — menyetujui atau mengembalikan | `owner` | Review |
| `finance` | **Viewer** — membaca antrean, riwayat, dan log keputusan | `finance` | History |

### 1.1 Matriks hak akses

| Fitur / Halaman | Purchasing (Maker) | Owner (Checker) | Finance (Viewer) |
| :--- | :---: | :---: | :---: |
| **Landing Page** (sebelum login) | ✅ | ✅ | ✅ |
| **Today** (antrean + Inspector) | ✅ | ✅ | ✅ |
| **Add Requests** (tempel teks → Organize → simpan) | ✅ | ✅ | ❌ tombol disembunyikan, API 403 |
| **Quick Check** (dry-run, tidak menyimpan) | ✅ | ❌ | ❌ |
| **Vendor quotes** (unggah penawaran PDF/XLSX) | ✅ | ❌ | ❌ |
| **Import Excel/CSV** (riwayat pembelian) | ✅ | ❌ | ❌ |
| **Review** (daftar menunggu keputusan) | ❌ | ✅ | ❌ |
| **Approve / Return** | ❌ | ✅ — **kecuali request yang ia buat sendiri (403)** | ❌ |
| **Recheck** (cek ulang baris yang sudah diputuskan) | ✅ hanya request miliknya | ✅ semua baris | ❌ |
| **History** | ✅ | ✅ | ✅ |
| **Audit Log** (+ unduh CSV) | ❌ tab tidak muncul, API 403 | ✅ | ✅ |

Catatan: Owner **boleh** membuat request. Karena itu aturan "tidak boleh menyetujui request buatan sendiri" adalah penjaga Maker-Checker yang sebenarnya.

### 1.2 Skema bisnis: kondisi input → perilaku sistem

Semua angka dihitung di Python (`checker.py`, `flags.py`, `pricing.py`); model hanya membaca teks dan mencocokkan listing.

| Kondisi input | Yang dilakukan sistem | Status / flag |
| :--- | :--- | :--- |
| **Barang cocok dengan katalog dan punya riwayat pembelian** | Referensi = rata-rata **3 pembelian terakhir**. Web check **tidak** dipanggil. | `checked` bila tidak ada flag, `flagged` bila ada flag |
| **Barang baru / tanpa riwayat** (dengan atau tanpa harga) | Web check: cache dulu (maks 60 hari), jika kosong Maker flow + Serper. Referensi = **median** dari minimal **3** listing yang lolos pengecekan bukti. | `new` bila tanpa flag, `flagged` bila ada flag |
| **Web check dapat kurang dari 3 listing** | Tidak ada referensi, `diff_pct` kosong, flag harga tidak bisa menyala. | `new` |
| **Langflow / Serper gagal** | Baris disimpan, pengecekan tidak dilanjutkan. | `pending` + pesan error |
| **Tanpa harga** | `diff_pct` kosong, `PRICE_ABOVE_REF` tidak bisa menyala. | tergantung flag lain |
| **Tanpa supplier** | `NEW_SUPPLIER` tidak bisa menyala. | tergantung flag lain |
| **Supplier disebut tetapi belum punya pembelian** | `NEW_SUPPLIER` (+10 risk). | `flagged` |
| **Harga > 15% di atas referensi** | `PRICE_ABOVE_REF` (+30 risk). | `flagged` |
| **Stok cukup untuk > 1 bulan pemakaian** | `STOCK_COVER_HIGH` (+20 risk). | `flagged` |
| **Qty > 2× median pembelian lalu** | `QTY_UNUSUAL` (+15 risk). | `flagged` |

**Risk score (0–100)** = jumlah bobot flag + `min(int(|diff_pct|), 20)`, maksimum 100. Contoh baris oli hidrolik: 30 + 20 + 20 = **70**.

**Aturan keputusan Owner:** menyetujui baris yang `flagged` atau ber-risk ≥ 50 adalah *override*: **wajib alasan dan tag hasil** (*False alarm* atau *Risk accepted*). Mengembalikan baris wajib alasan. Setiap keputusan masuk ke Audit Log yang tidak bisa diubah lewat aplikasi, lengkap dengan potret bukti saat keputusan dibuat.

---

## Bagian 2: Naskah Video Demo (≈ 4,5 menit)

### Persiapan sebelum merekam (jangan dilewati)

| # | Langkah | Mengapa |
| :--- | :--- | :--- |
| 1 | `./start.sh` lalu pastikan DB, backend, Langflow, frontend menyala | — |
| 2 | **Impor ulang `langflow/Maker.json`** ke Langflow dan salin Flow ID ke `LANGFLOW_MAKER_FLOW_ID` | Export sebelumnya tidak punya output `extract_json`, sehingga web check selalu gagal. Sudah diperbaiki di repo; flow di Langflow Anda harus diperbarui juga |
| 3 | Pada setiap node *Language Model*: pilih provider dan model yang dimaksud, temperature 0 | Export berbeda-beda (Maker: Claude Haiku; Organize: gateway OpenAI-compatible) |
| 4 | `cd backend && python -m app.flowcheck` | Memastikan Organize dan Maker menjawab sesuai kontrak |
| 5 | `python -m app.seed --reset --empty-today` | Riwayat dan stok ada, antrean hari ini kosong. Kutipan web untuk *Solenoid valve* tersimpan di cache |
| 6 | **Latih** langkah Add Requests satu kali dengan teks di Adegan 2 | Organize bisa mengubah nama barang ke Bahasa Inggris (lihat Bagian 3). Teks demo sengaja memakai nama barang yang sama dengan katalog |
| 7 | Jangan salah ketik password lebih dari 4 kali per menit | Login dibatasi 5 percobaan per menit per IP |
| 8 | Token berlaku 1 jam | Rekam dalam satu sesi; jika kembali ke layar login, masuk lagi |
| 9 | Buka browser di `http://localhost:5173`, **belum login** | — |

### 🎬 Adegan 1: Pembukaan & masalah (0:00 – 0:30)
**Tampilan:** Landing Page Procur.AI.
**Narasi:**
> *"Perusahaan menengah tanpa ERP sering bocor anggaran karena belanja lewat WhatsApp tanpa catatan: harga lebih mahal dari biasanya, stok yang sebenarnya masih banyak, atau supplier yang tidak jelas. Procur.AI memeriksa setiap permintaan sebelum uang keluar. AI membaca bahasa, Python menghitung angka, dan keputusan akhir ada di tangan manusia."*

### 🎬 Adegan 2: Alur Maker / Purchasing (0:30 – 1:50)
**Aksi:**
1. Klik tombol login di Landing Page → login `purchasing`.
2. Tunjukkan menu: **Today, Quick check, Vendor quotes, History, Import** (tidak ada Review dan Audit Log).
3. Klik **Add requests**, tempel (nama barang sengaja sama dengan katalog):
   ```
   1. Hydraulic oil ISO VG 46, 20L – 4 drum, Warehouse, Rp 1.450.000/drum, CV Sinar Pelumas
   2. Solenoid valve 24V DC, 1/2" – 2 pcs, Maintenance
   ```
4. Klik **Organize**. **Periksa nama barang di tabel pratinjau** dan perbaiki langsung bila model menerjemahkannya. Klik **Save and check**.
5. Klik baris **Hydraulic oil**, tunjukkan Inspector. Klik baris **Solenoid valve**.

**Yang akan terlihat (hasil seed, diverifikasi):**
- Oli hidrolik: status **Flagged**, selisih **+29,5%** terhadap rata-rata 3 pembelian terakhir (**Rp 1.120.000**), flag **PRICE_ABOVE_REF** dan **STOCK_COVER_HIGH**, **Risk Score 70/100**.
- Solenoid valve: barang baru tanpa riwayat → status **New**, referensi dari **median kutipan web (Rp 425.000)**, tanpa flag.
- Nama supplier di panel detail tampil tersamar (PII masking, mis. `CV S**** P******`). Jangan buka *Compare suppliers*: panel itu menampilkan nama apa adanya.
- Di tempat tombol Approve muncul tulisan **"Waiting for approval"**.

**Narasi:**
> *"Sebagai staf purchasing, saya memasukkan permintaan. AI mengubah teks bebas menjadi baris terstruktur, lalu mesin pengecek memakai riwayat pembelian kami. Oli ini 29,5% lebih mahal dari rata-rata tiga pembelian terakhir dan stoknya masih cukup untuk sekitar enam minggu, sehingga skor risikonya 70 dari 100. Perhatikan: saya sebagai Maker tidak punya tombol Approve. Untuk solenoid valve yang belum pernah kami beli, sistem memakai median harga marketplace yang terverifikasi, bukan angka karangan model."*

*(Opsional, +20 detik, butuh Serper aktif: tambahkan satu barang baru lain, mis. "helm proyek putih 5 pcs", dan tunjukkan kutipan web atau pesan bahwa kutipan kurang dari 3 sehingga tidak ada referensi. Hasilnya bergantung pada pencarian langsung, jadi jangan dijadikan satu-satunya bukti.)*

### 🎬 Adegan 3: Quick Check (1:50 – 2:15)
**Aksi:** Buka **Quick check**. Tempel `oli hidrolik 46 20L 4 drum @1,45jt dari CV Sinar Pelumas` (contoh yang sudah ada di kolom isian). Klik **Organize**, lalu **Check**.
**Narasi:**
> *"Quick Check adalah uji coba tanpa menyimpan apa pun: berguna sebelum menawar. Fitur ini khusus Purchasing."*

### 🎬 Adegan 4: Alur Checker / Owner (2:15 – 3:30)
**Aksi:**
1. **Logout** → login `owner`. Halaman awal: **Review**. Tunjukkan menu: **Review, Today, History, Audit Log**.
2. Daftar Review menampilkan baris *flagged* paling atas, lalu berdasarkan risk score. Pilih **Hydraulic oil**.
3. Klik **Approve with reason**. Dialog **"Approve despite flags"** muncul: isi **Reason**, pilih tag **False alarm** atau **Risk accepted**, klik **Approve**.
   Contoh alasan: *"Vendor menaikkan harga resmi bulan ini; stok akan dikurangi pada pembelian berikutnya."* dengan tag **Risk accepted**.
4. Pilih baris lain (mis. **Solenoid valve**) dan tunjukkan **Return to requester**: alasan wajib diisi.
5. *(Opsional)* Owner membuat request sendiri lewat **Add requests**, lalu mencoba menyetujuinya → ditolak: *"You cannot approve a request you created"*.

**Narasi:**
> *"Sekarang saya Owner, pemeriksa independen. Baris berisiko tertinggi muncul paling atas. Karena baris ini bertanda flag, sistem memaksa saya menulis alasan dan memilih apakah ini alarm palsu atau risiko yang saya terima. Saya juga tidak bisa menyetujui request yang saya buat sendiri, sehingga satu orang tidak bisa mengajukan sekaligus menyetujui."*

### 🎬 Adegan 5: Audit Log & Finance (3:30 – 4:05)
**Aksi:**
1. Klik **Audit Log**. Tunjukkan kolom: **Waktu, User, Aksi, Nama Barang, Alasan, Outcome, Risk, Flags**. Klik **Download CSV**.
2. Buka baris oli di Inspector dan tunjukkan riwayat keputusan, termasuk baris ringkasan yang diawali *"At decision:"* (risk 70/100, dua flag, harga referensi dan sumbernya). Bunyi persisnya mengikuti `snapshotLine()` di `frontend/src/lib/decisions.ts`.
3. **Logout** → login `finance`. Halaman awal: **History**. Menu: **Today, History, Audit Log**. Tombol **Add requests** tidak ada. Di Today, baris yang belum diputuskan hanya menampilkan "Waiting for approval".

**Narasi:**
> *"Setiap keputusan tercatat: siapa, kapan, alasannya, dan apa yang dilihat pemutus saat itu. Catatan ini tidak bisa diubah lewat aplikasi. Finance hanya membaca dan mengaudit; mereka tidak bisa membuat maupun menyetujui."*

### 🎬 Adegan 6: Pengukuran kualitas & penutup (4:05 – 4:35)
**Tampilan:** `backend/eval/results.md` di editor atau terminal (`python -m eval.run --suite E1,E2,E3,E4`).
**Narasi (versi jujur, sesuai hasil terukur 31 Oktober):**
> *"Kami tidak hanya membangun, kami mengukur. Pada uji ekstraksi dengan 3 pesan dan 5 baris, kuantitas, satuan, harga, supplier, dan departemen terbaca 100%. Tetapi nama barang hanya 20%, karena model menerjemahkan nama Indonesia ke Bahasa Inggris. Temuan ini datang dari evaluasi kami sendiri, dan perbaikan model serta prompt Organize sedang dikerjakan. Kami juga sudah menyiapkan pengukuran akurasi harga web (MAPE); kumpulan harga manual untuk mengujinya masih dikumpulkan, jadi belum ada angkanya. Procur.AI: cegah kebocoran anggaran sebelum uang keluar. Terima kasih."*

> **Jika perbaikan Organize sudah selesai sebelum merekam:** jalankan ulang `python -m eval.run --suite E1`, lalu ganti angka di atas dengan **angka yang tertulis di `eval/results.md` hasil run baru** beserta jumlah baris sampelnya. Jangan menulis angka sebelum run itu ada.

---

## Bagian 3: Klaim yang boleh dan tidak boleh diucapkan

| ❌ Jangan katakan | Alasan | ✅ Katakan |
| :--- | :--- | :--- |
| "Akurasi ekstraksi AI 100%" (versi lama naskah) | Terukur 20% untuk nama barang (5 baris); skrip `eval_llm.py` yang menghasilkan "100%" sudah dihapus dan memakai metode berbeda | Tabel per kolom beserta jumlah sampelnya (Adegan 6) |
| Angka MAPE harga web, apa pun nilainya | Suite E3 dilewati (*skipped*): belum ada harga manual, **belum ada MAPE** | "Alat ukurnya siap, datanya sedang dikumpulkan" |
| "Semua angka 100% akurat karena dihitung Python" | Python menghitung dengan tepat, tetapi dari masukan yang dibaca model (E1b: satu flag berubah karena nama salah baca) | "Angka dihitung di Python dari masukan yang diekstrak; ekstraksi diukur terpisah" |
| "Quick Check dan Import bisa dipakai semua peran" (versi lama) | Hanya `purchasing` | Gunakan matriks Bagian 1.1 |
| "Supplier baru menambah risk +25" (versi lama) | Bobot `NEW_SUPPLIER` adalah **10** | Bobot: harga +30, stok +20, qty +15, supplier baru +10, ditambah maks 20 dari besarnya selisih |
| "Claude Haiku menjalankan semua flow" | `Maker.json`: Claude Haiku. `Organize.json` dan `Web Check.json`: gateway OpenAI-compatible, kecuali sudah diekspor ulang | Sebutkan model per flow sesuai yang tertulis di `eval/results.md` |
| "Audit log tidak bisa diubah siapa pun" | Dijaga di lapisan aplikasi (ORM). Administrator database dengan akses SQL langsung masih bisa mengubahnya | "Tidak bisa diubah lewat aplikasi" |

## Rencana cadangan saat merekam

| Masalah | Penanganan |
| :--- | :--- |
| Organize menerjemahkan nama barang | Edit nama di tabel pratinjau sebelum **Save and check**. Jangan tutupi: sebutkan bahwa ini temuan evaluasi (Adegan 6) |
| Langflow mati atau Serper habis kuota | Baris tersimpan sebagai `pending` dengan pesan error. Gunakan seed lengkap `python -m app.seed --reset` (tanpa `--empty-today`) sehingga lima baris hari ini sudah ada, dan mulai rekaman dari Adegan 2 langkah 5 |
| Web check menemukan kurang dari 3 listing | Status **New** tanpa referensi adalah perilaku yang benar. Gunakan *Solenoid valve* yang kutipannya sudah ada di cache |
| Kembali ke layar login di tengah rekaman | Token habis (1 jam). Login lagi dan lanjutkan |
| Tombol Approve tidak muncul untuk Owner | Baris itu sudah berstatus Approved/Returned, atau Anda login sebagai peran lain |
