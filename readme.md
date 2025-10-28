# XSS-Automator

XSS-Automator — toolkit pemindaian XSS asinkron dengan verifikasi Playwright dan kontrol penuh melalui bot Telegram.
Dirancang untuk peneliti keamanan dan penguji penetrasi (gunakan hanya dengan otorisasi eksplisit).

## Fitur

- Crawling & pemindaian asinkron (asyncio, httpx)
- Penambangan parameter dan enumerasi form (GET/POST/FORM)
- Mesin injeksi dengan bank payload yang dapat dikonfigurasi
- Verifikasi DOM menggunakan Playwright (mendukung screenshot)
- Integrasi penuh bot Telegram untuk kontrol jarak jauh dan notifikasi
- Pelaporan JSON + HTML (screenshot disimpan ke disk)
- Dapat dikonfigurasi melalui config.yaml

## Instalasi

### Clone repository

```bash
git clone https://github.com/satrioun/xss-automator.git
cd xss-automator
```

### Buat Virtual Environment

**Windows:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### (Opsional) Install Browser Playwright

Jika Anda berencana menggunakan verifikasi DOM, install browser:

```bash
playwright install chromium
# atau
python -m playwright install chromium
```

## Konfigurasi

Edit `config.yaml` untuk menyesuaikan opsi pemindaian dan telemetri. Bagian kunci:

- `target.base_url` — URL dasar situs target
- `crawler.*` — batasan crawling dan timeout
- `injection.*` — template marker, payload per input, maksimal injeksi/halaman
- `verification.*` — aktifkan Playwright, confidence minimum, timeout
- `report.*` — tempat menyimpan laporan JSON/HTML dan screenshot
- `telemetry.telegram` — konfigurasi bot Telegram

### Contoh snippet konfigurasi

(set `bot_token_env` ke nama environment variable yang menyimpan token):

```yaml
telemetry:
  telegram:
    bot_token_env: "BOT_TOKEN"
    allowed_chat_ids:
      - 123456789
    notify_on_find: true
    notify_on_finish: true
```

## Setup Bot Telegram

### 1. Buat bot dengan @BotFather

### 2. Set environment variable untuk token

**Windows (PowerShell):**
```powershell
setx BOT_TOKEN "123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxx"
# Mulai sesi terminal baru atau buka kembali PowerShell untuk menggunakan variabel.
```

**Linux / macOS:**
```bash
export BOT_TOKEN="123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### 3. Tambahkan chat_id Telegram Anda

Tambahkan chat_id Anda ke `config.yaml` di bawah `telemetry.telegram.allowed_chat_ids`. 

Anda bisa mendapatkan chat ID dengan tools seperti @CekIDTelegram_bot atau dengan menjalankan bot dan mengirim pesan apapun (cek log untuk payload update).

## Penggunaan

### Jalankan dari CLI

```bash
# Jalankan scan dengan config.yaml dan mulai scan segera
python main.py --config config.yaml --scan --base-url http://example.com
```

### Kontrol dari Telegram

(jika sudah dikonfigurasi dan chat id diizinkan):

- `/start` — tampilkan bantuan
- `/help` — tampilkan perintah
- `/scan [url]` — mulai pemindaian (menggunakan base_url config jika tidak disebutkan)
- `/status` — dapatkan status saat ini
- `/stop` — hentikan pemindaian yang sedang berjalan
- `/report` — dapatkan file laporan terbaru
- `/confirm_active` — konfirmasi pemindaian aktif (jika keamanan memerlukannya)

## Output & Laporan

- Laporan JSON dan HTML ditulis ke `report.out_dir` (default `./reports`)
- Screenshot (jika Playwright digunakan) disimpan ke `report.screenshot_dir`
- Nama file menyertakan timestamp untuk menghindari tabrakan
- Path laporan terbaru dapat diakses melalui perintah `/report` di Telegram

## Keamanan & Legal

⚠️ **PENTING:** Anda HARUS memiliki izin eksplisit untuk memindai target apapun. Menjalankan tool ini terhadap sistem yang tidak Anda miliki atau tidak memiliki otorisasi untuk menguji adalah **ilegal dan tidak etis**.

Tool ini mencakup opsi konfigurasi untuk mengurangi perilaku destruktif (misalnya `safety.require_telegram_confirm_for_active`). Gunakan opsi tersebut.

## Troubleshooting

### AsyncClient.__init__() got an unexpected keyword argument 'proxies'
Pastikan versi httpx yang kompatibel (direkomendasikan `httpx>=0.27.0`) dan kompatibilitas python-telegram-bot. Gunakan `requirements.txt` yang disediakan.

### Error browser Playwright
Jalankan: `playwright install chromium`

### Telegram 401 Unauthorized
Verifikasi BOT_TOKEN dan pastikan token sudah diset dengan benar di environment.

### Error event loop (already running)
Jalankan main dalam satu event loop asyncio — kode repository menangani ini; hindari eksekusi di dalam environment interaktif yang sudah berjalan.

## Kontribusi

Kontribusi sangat disambut baik. Mohon buka issue terlebih dahulu untuk mendiskusikan perubahan besar. Ikuti gaya coding repository dan tambahkan test jika memungkinkan.

## Lisensi

Dirilis di bawah MIT License. Lihat LICENSE untuk detail.

## Kontak
📱 Instagram: [@riocns](https://www.instagram.com/riocns)
---

**CATATAN:** README ini mengasumsikan Anda sudah memiliki kode repository. Sesuaikan URL git clone dan informasi author dengan proyek Anda sebelum push ke GitHub.