# Figma API Playground

## Ringkasan

Figma API Playground adalah tool lokal untuk mengambil, merapikan, dan mengekspor flow dari file Figma agar lebih mudah dipakai di FUT Automation.

Tool ini dibuat untuk mengurangi proses manual ketika user harus membuka Figma, memilih section/flow, mengekspor PDF atau PNG satu per satu, lalu mengunggah hasilnya ke FUT Automation. Dengan Playground, flow dari Figma bisa dikumpulkan lebih cepat, lebih rapi, dan lebih siap digunakan sebagai input visual untuk proses AI/OCR atau generate test case.

Secara sederhana:

```text
Figma file -> pilih page/section/flow -> export visual PNG/ZIP/PDF -> siap dipakai di FUT Automation
```

## Tujuan

Tujuan utama Figma API Playground adalah menjadi jembatan antara desain Figma dan FUT Automation.

FUT Automation membutuhkan input visual agar AI/OCR dapat membaca tampilan UI, memahami screen, flow, input, popup, error/success state, dan expected result. Karena struktur JSON Figma saja belum cukup untuk kebutuhan black-box testing, Playground membantu mengubah desain Figma menjadi asset visual yang lebih mudah diproses.

## Dua Metode Load Figma

### 1. Lewat Figma Plugin

Metode ini adalah pendekatan yang lebih disarankan untuk mengurangi ketergantungan pada Figma Personal Access Token.

Alur kerja:

1. User membuka file Figma.
2. User menjalankan plugin `FUT Section Exporter`.
3. User memilih page yang ingin diexport.
4. Plugin mengekspor section/frame sebagai PNG ZIP.
5. Plugin mengirim hasil export ke Playground lokal di `http://127.0.0.1:5050`.
6. Playground menerima hasil export sebagai plugin import.
7. User dapat melihat, mengurutkan, menyembunyikan, menghapus, atau membuka ZIP hasil import.

Kelebihan metode plugin:

- Tidak memakai Figma Personal Access Token.
- Tidak bergantung pada Figma Images API untuk render dari server.
- Lebih cocok untuk menghindari masalah rate limit Figma API.
- Hasil yang diterima sudah berupa visual PNG.
- Bisa export beberapa page sekaligus.
- Setiap page diterima sebagai import terpisah agar flow tetap rapi.

Catatan:

- User tetap harus memiliki akses edit/owner pada file Figma agar plugin development bisa dijalankan.
- Plugin dijalankan dari aplikasi Figma, bukan dari server.
- Data dikirim ke server lokal Playground, bukan ke GitHub dan bukan langsung ke Figma API.

### 2. Lewat Figma API

Metode ini menggunakan Figma Personal Access Token dan file key/URL Figma.

Alur kerja:

1. User memasukkan judul Figma.
2. User memasukkan Figma Personal Access Token.
3. User memasukkan Figma file URL atau file key.
4. Playground membaca struktur file menggunakan Figma API.
5. User dapat melihat pages, sections, dan frames.
6. User dapat render preview atau export JSON/PDF sesuai kebutuhan.

Kelebihan metode API:

- Bisa membaca struktur file Figma secara langsung.
- Bisa menyimpan Saved Figma lokal agar token/file key tidak perlu diketik ulang.
- Bisa download snapshot JSON untuk eksplorasi struktur tanpa memanggil Figma API lagi.

Kekurangan metode API:

- Tetap memakai Personal Access Token.
- Load dan render dapat terkena rate limit Figma API.
- Snapshot JSON tidak bisa menggantikan render visual sepenuhnya.
- Export PDF/render visual tetap membutuhkan token-backed session.

## Fitur Utama

### Login Lokal

Playground memiliki login lokal untuk membatasi akses aplikasi di laptop/server lokal.

Default login:

```text
Username: admin
Password: a52s12145
```

Password dapat diubah melalui environment variable `FIGMA_PLAYGROUND_PASSWORD`.

### Saved Figma

Saved Figma menyimpan data Figma secara lokal agar user tidak perlu memasukkan token dan file key berulang kali.

Data yang disimpan:

- Judul Figma.
- Figma Personal Access Token.
- Figma file URL/file key.
- Metadata file.

Catatan penting:

- Saved Figma disimpan lokal di laptop.
- Data ini tidak boleh dipush ke Git.
- `Load Saved` tetap memanggil Figma API lagi, sehingga masih bisa terkena rate limit.

### Snapshot JSON

Snapshot JSON adalah salinan struktur file Figma yang pernah berhasil diload.

Fungsi snapshot:

- Membaca ulang struktur Figma tanpa memanggil API.
- Mengurangi penggunaan rate limit ketika hanya perlu melihat pages/sections/frames.
- Cocok untuk eksplorasi data struktur.

Batasan snapshot:

- Snapshot tidak menyimpan Personal Access Token.
- Snapshot tidak bisa melakukan render visual baru.
- Snapshot tidak cukup untuk export PDF visual jika tidak ada token-backed session aktif.

### Plugin Import

Plugin Import adalah area untuk menerima hasil export dari Figma plugin.

Fitur Plugin Import:

- Menerima ZIP PNG dari plugin.
- Menampilkan preview hasil export.
- Import baru tidak menimpa import lama.
- Import dapat dihapus.
- Import dapat diurutkan ulang dengan tombol Up/Down atau drag handle.
- Gambar tertentu dapat disembunyikan dengan tombol Hide.
- Gambar tersembunyi dapat dikembalikan dengan Restore Hidden.
- ZIP asli dapat dibuka/download kembali melalui Open ZIP.

## Data Flow Plugin

```text
Figma Desktop/Web
  -> FUT Section Exporter Plugin
  -> Export selected page/section/frame to PNG ZIP
  -> POST ZIP binary to http://127.0.0.1:5050/api/plugin-import
  -> Playground stores import locally
  -> User reviews and organizes export result
  -> Output ready for FUT Automation
```

Data plugin masuk ke server lokal `localhost:5050`. Data tidak dikirim ke GitHub dan tidak dikirim ke Figma API oleh Playground.

## Data Flow Figma API

```text
User input token + file key
  -> Playground calls Figma API
  -> Figma returns file structure JSON
  -> Playground extracts pages/sections/frames
  -> Optional render/export uses Figma render API
  -> Output JSON/PDF/preview for FUT Automation
```

## Keamanan

### Yang Disembunyikan dari Git

File dan folder berikut tidak boleh dipush ke Git:

- `.env`
- `.env.*`
- `data/`
- session store lokal
- token vault lokal
- file runtime/log lokal
- hasil import plugin lokal

### Token Handling

Personal Access Token hanya digunakan untuk metode Figma API.

Pada metode plugin, user tidak perlu memasukkan token. Plugin mengirim hasil visual PNG/ZIP langsung ke Playground lokal.

Untuk production/internal multi-user, token server tidak boleh dikirim ke plugin. Jika butuh deployment production, gunakan HTTPS, SSO/internal reverse proxy, dan short-lived upload credential dari sisi server.

## Posisi dalam FUT Automation

Dalam proses FUT Automation, Playground berfungsi sebagai alat bantu sebelum generate test case.

Peran Playground:

1. Mengambil flow dari Figma.
2. Mengubah flow menjadi asset visual.
3. Menyusun asset sesuai urutan journey/scenario.
4. Menyiapkan output agar dapat dipakai oleh AI/OCR di FUT Automation.

Dengan pendekatan ini, user tidak perlu melakukan export manual satu per satu dari Figma seperti proses konvensional.

## Output yang Dihasilkan

Output yang dapat dihasilkan Playground:

- PNG dari hasil plugin export.
- ZIP berisi PNG hasil export.
- JSON struktur Figma.
- Snapshot JSON lokal.
- PDF per section dari metode Figma API jika session token aktif.

## Kesimpulan

Figma API Playground adalah bridge antara desain Figma dan FUT Automation. Tool ini membantu mengubah desain Figma yang awalnya berupa struktur desain atau canvas visual menjadi asset yang lebih siap dipakai untuk proses testing berbasis AI/OCR.

Metode plugin menjadi pendekatan yang lebih praktis untuk menghindari masalah Personal Access Token dan rate limit, sedangkan metode Figma API tetap tersedia untuk kebutuhan membaca struktur file, snapshot, dan render berbasis API.
