# Tomato Leaf Dataset Preparation Script

Repotori ini berisi script Python `prepare_dataset.py` yang dirancang untuk membersihkan, melakukan deduplikasi, memvalidasi integritas gambar, dan membagi dataset klasifikasi gambar daun tomat secara terstruktur dan proporsional (stratified split).

![Grafik akurasi](result/distribusi_dataset.png)
## Fitur Utama
1. **Normalisasi Nama Kelas**: Mengubah folder kelas asli menjadi format lowercase dan snake_case.
2. **Validasi Gambar**: Mendeteksi gambar yang rusak/corrupt menggunakan library `Pillow` (`PIL.Image`).
3. **Deduplikasi SHA-256**: Mendeteksi gambar duplikat di dalam seluruh dataset berdasarkan nilai hash berkas.
4. **Pembagian Data Stratified (80/10/10)**: Membagi data menjadi Train (80%), Validation (10%), dan Test (10%) dengan mempertahankan distribusi kelas secara proporsional menggunakan `scikit-learn`.
5. **Dukungan Concurrency**: Proses penyalinan file dapat dilakukan secara paralel menggunakan multi-threading untuk meningkatkan performa.
6. **Laporan CSV dan JSON**: Menghasilkan 5 jenis laporan detail mengenai ringkasan dataset, file corrupt, file duplikat, manifest pembagian, dan pemetaan kelas.
7. **Kompatibilitas**: Mendukung Windows (Command Prompt & PowerShell) serta Google Colab.

---

## Struktur Output Hasil
Setelah dijalankan, script akan menghasilkan folder output dengan struktur berikut:

```text
dataset_clean/
├── train/
│   ├── bacterial_spot/
│   ├── early_blight/
│   ├── healthy/
│   ├── late_blight/
│   ├── leaf_mold/
│   ├── septoria_leaf_spot/
│   ├── target_spot/
│   ├── tomato_mosaic_virus/
│   ├── tomato_yellow_leaf_curl_virus/
│   └── two_spotted_spider_mite/
├── validation/
│   └── (seluruh folder kelas yang sama)
├── test/
│   └── (seluruh folder kelas yang sama)
└── reports/
    ├── dataset_summary.csv
    ├── corrupt_files.csv
    ├── duplicate_files.csv
    ├── split_manifest.csv
    └── class_mapping.json
```

Nama file hasil salinan di setiap split akan diatur secara berurutan dan konsisten:
- `bacterial_spot_000001.jpg`
- `bacterial_spot_000002.jpg`
- `early_blight_000001.jpg`

---

## Petunjuk Penggunaan

### 1. Instalasi Dependensi
Pastikan Python 3 telah terinstal. Pasang pustaka pihak ketiga yang diperlukan menggunakan perintah berikut:

```bash
pip install -r requirements.txt
```

Isi dari `requirements.txt`:
```text
Pillow>=10.0.0
scikit-learn>=1.0.0
```

### 2. Parameter Command Line (Argumen)
Script ini menyediakan beberapa argumen opsional:
- `--source`: Lokasi dataset sumber utama (Default: `"Dataset of Tomato Leaves/plantvillage/Preprocessed data"`).
- `--output`: Lokasi folder output hasil pembersihan (Default: `"dataset_clean"`).
- `--train-ratio`: Rasio subset Train (Default: `0.8`).
- `--val-ratio`: Rasio subset Validation (Default: `0.1`).
- `--test-ratio`: Rasio subset Test (Default: `0.1`).
- `--seed`: Angka acak/random seed untuk reproduktibilitas hasil (Default: `42`).
- `--overwrite`: Menghapus folder output jika sudah ada sebelumnya dan membuat ulang.
- `--dry-run`: Hanya menjalankan simulasi pengecekan gambar, deduplikasi, pembagian, dan menampilkan tabel sebaran kelas tanpa menyalin berkas asli ke disk.
- `--copy-workers`: Jumlah worker thread untuk proses penyalinan file secara paralel (Default: `4`).

### 3. Cara Menjalankan

#### A. Menjalankan Simulasi (Dry Run)
Sebelum menyalin ribuan file, Anda dapat menjalankan simulasi terlebih dahulu untuk memeriksa hasil statistik pembagian kelas:

```bash
python prepare_dataset.py --dry-run
```

#### B. Penggunaan di Windows PowerShell
Jalankan perintah berikut untuk merapikan dataset asli ke folder baru `dataset_clean/`:

```powershell
python prepare_dataset.py `
    --source "Dataset of Tomato Leaves\plantvillage\Preprocessed data" `
    --output "dataset_clean" `
    --train-ratio 0.8 `
    --val-ratio 0.1 `
    --test-ratio 0.1 `
    --seed 42 `
    --overwrite
```

#### C. Penggunaan di Google Colab / Linux
Di sel kode Google Colab, Anda dapat memasang dependensi dan memicu pembersihan dengan:

```python
# Install dependencies
!pip install Pillow scikit-learn

# Jalankan script
!python prepare_dataset.py \
    --source "Dataset of Tomato Leaves/plantvillage/Preprocessed data" \
    --output "dataset_clean" \
    --train-ratio 0.8 \
    --val-ratio 0.1 \
    --test-ratio 0.1 \
    --seed 42 \
    --overwrite
```

---

## Penjelasan Berkas Laporan (`reports/`)
1. **`dataset_summary.csv`**: Statistik sebaran jumlah gambar per kelas (original, valid, corrupt, duplicate, train, validation, test).
2. **`corrupt_files.csv`**: Daftar berkas gambar yang rusak/tidak dapat dibuka beserta letak berkas dan pesan kesalahan detailnya.
3. **`duplicate_files.csv`**: Daftar gambar duplikat, hash SHA-256 berkas, nama kelas, dan rujukan ke berkas gambar asli pertama.
4. **`split_manifest.csv`**: Pemetaan lokasi gambar sumber asli, nama split (train/validation/test), lokasi salinan berkas baru, dan nilai hash SHA-256 masing-masing.
5. **`class_mapping.json`**: File konversi / pemetaan nama folder asli dengan format kelas snake_case baru yang dirapikan.
