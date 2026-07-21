# FUT Exporter

Local Figma plugin untuk export node dari current page menjadi ZIP berisi PNG + `manifest.json`.

Plugin ini tidak memakai Personal Access Token dan tidak memanggil Figma REST API.

## Cara Import ke Figma Desktop

1. Buka Figma Desktop.
2. Buka file Figma duplicate yang kamu own.
3. Menu kiri atas: `Plugins -> Development -> Import plugin from manifest...`
4. Pilih file: `figma-plugin-fut-section-exporter/manifest.json`
5. Jalankan: `Plugins -> Development -> FUT Section Exporter`

## Cara Pakai

1. Buka page yang berisi flow.
2. Run plugin.
3. Pilih depth:
   - `Level 1 only`: node paling atas di page, misalnya `V-NSP Playlist`.
   - `Level 1-2`: termasuk child level 2, misalnya `MVP (1 Jul 2026)`.
   - `Level 1-3`: termasuk child level 3.
4. Gunakan tombol cepat:
   - `All`
   - `Level 1`
   - `Level 2`
   - `Level 3`
5. Pilih scale:
   - `0.5x` default aman.
   - `0.25x` untuk node besar.
   - `1x` untuk kualitas tinggi.
6. Klik `Export ZIP`.

Output ZIP:

```text
fut-nodes-<page>.zip
  flow-01-<node>.png
  flow-02-<node>.png
  manifest.json
```

## Catatan

- Plugin scan node exportable: `SECTION`, `FRAME`, `COMPONENT`, `INSTANCE`, dan `GROUP`.
- Plugin bekerja pada current page yang sedang dibuka.
- Kalau struktur node terlalu dalam, pilih `Level 1-4`.
