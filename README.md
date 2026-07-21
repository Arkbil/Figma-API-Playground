# FINTA

FINTA adalah tool lokal untuk mengambil flow dari Figma dan menyiapkannya sebagai output visual untuk FUT Automation.

FINTA membantu menggantikan proses manual seperti membuka Figma, memilih section/flow, export file satu per satu, lalu menyiapkannya untuk generate test case atau analisis AI/OCR.

```text
Figma -> FINTA -> PNG/ZIP/PDF/JSON -> FUT Automation
```

## Cara Menjalankan

Jalankan dari folder project ini:

```powershell
cd figma-api-playground
python app.py
```

Buka di browser:

```text
http://127.0.0.1:5050
```

Default login lokal:

```text
Username: admin
Password: a52s12145
```

Password dapat diganti melalui environment variable `FIGMA_PLAYGROUND_PASSWORD`.

## Dua Mode Utama

### 1. FINTA Exporter Plugin

Mode plugin digunakan untuk mengambil visual langsung dari file Figma yang sedang dibuka.

Alur singkat:

1. Buka file Figma.
2. Jalankan plugin `FINTA Exporter`.
3. Pilih page/flow yang ingin diexport.
4. Centang bagian yang dibutuhkan.
5. Klik `Send to FINTA` atau `Download ZIP`.
6. Hasil import muncul di FINTA sebagai ZIP/PNG lokal.

Kelebihan mode plugin:

- Tidak memakai Figma Personal Access Token.
- Lebih aman dari masalah rate limit Figma REST API.
- Output sudah berupa gambar visual.
- Cocok untuk kebutuhan FUT Automation yang membutuhkan input visual.

Output plugin:

```text
manifest.json
flow-01-example.png
flow-02-example.png
flow-03-example.png
```

### 2. Figma API Mode

Mode API digunakan untuk mengambil struktur file Figma memakai file key dan Personal Access Token.

Mode ini membaca:

- page
- section
- frame
- struktur file Figma

Output yang bisa dibuat:

- JSON struktur Figma
- Snapshot JSON
- Preview render
- PDF per section
- ZIP hasil export PDF

Catatan: mode ini tetap memakai Personal Access Token, sehingga load, render, dan export masih bisa terkena limit Figma API.

## Saved Figma dan Snapshot

### Saved Figma

Saved Figma menyimpan token dan file key secara lokal agar user tidak perlu input ulang.

Penting:

- Data Saved Figma hanya untuk lokal.
- `Load Saved` tetap memanggil Figma API lagi.
- Saved token tidak boleh dipush ke Git.

### Snapshot JSON

Snapshot JSON menyimpan struktur file Figma yang sudah pernah berhasil diload.

Kegunaan:

- Membuka ulang struktur Figma tanpa memanggil API.
- Mengurangi penggunaan rate limit.
- Cocok untuk eksplorasi page, section, dan frame.

Batasan:

- Snapshot tidak menyimpan token.
- Snapshot tidak bisa render visual baru tanpa token/session aktif.

## Plugin Import

Bagian Plugin Import menerima hasil dari `FINTA Exporter`.

Fitur yang tersedia:

- melihat hasil PNG
- membuka ZIP asli
- menghapus import
- mengurutkan import
- menyembunyikan gambar tertentu
- restore gambar yang disembunyikan

Import plugin baru tidak menimpa import lama.

## Keamanan Git

File lokal berikut tidak boleh dikirim ke repository:

- `.env`
- `.env.*`
- `data/`
- `session_store.local.json`
- hasil import plugin lokal
- log server lokal
- database/cache lokal
- snapshot/export runtime lokal

Semua file tersebut sudah diatur di `.gitignore`.

Sebelum push, cek dengan:

```powershell
git status --short
```

Pastikan tidak ada file seperti berikut yang masuk daftar commit:

```text
.env
data/
server.local.log
server.local.err.log
session_store.local.json
plugin_imports/
```

## File Penting

```text
app.py                                  server lokal FINTA
templates/index.html                    struktur halaman web
static/app.js                           logic frontend
static/styles.css                       styling UI
figma-plugin-fut-section-exporter/      source plugin FINTA Exporter
.env.example                            contoh konfigurasi aman
data/                                   runtime lokal, di-ignore dari Git
```

## Production / Internal Use

Untuk penggunaan lokal, FINTA berjalan di:

```text
http://127.0.0.1:5050
```

Untuk production/internal multi-user:

1. Jalankan FINTA di balik HTTPS.
2. Gunakan SSO atau internal reverse proxy.
3. Jangan expose secret server ke plugin.
4. Jangan kirim token dari `.env` ke frontend/plugin.
5. Simpan hasil import di storage yang private.
6. Tambahkan cleanup/retention untuk file import lama.

`FIGMA_PLUGIN_UPLOAD_TOKEN` tetap tersedia untuk deployment terkontrol, tetapi plugin bawaan tidak meminta user mengetik token manual.

## Ringkasan

FINTA adalah bridge antara Figma dan FUT Automation.

Mode plugin cocok untuk mengambil output visual tanpa Personal Access Token. Mode API cocok untuk membaca struktur Figma langsung dari file key, tetapi tetap bergantung pada limit Figma API.
