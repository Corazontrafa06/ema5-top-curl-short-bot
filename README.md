# EMA5 Top-Curl SHORT 1H — Bot Alert Bybit

Bot **alert saja** (tanpa auto-trade, tanpa kode order, tanpa API key) yang memantau semua
USDT perpetual di Bybit dan kirim sinyal **SHORT** di timeframe **1H** saat:

1. **EMA5 kuning** berada **di atas EMA10 hijau dan EMA30 ungu**, lalu
2. EMA5 **nukik turun untuk pertama kali** sejak naik ke atas.

Level tiap sinyal:

| | |
|---|---|
| Entry | harga saat alert |
| SL | **+8%** |
| TP1 | **−3%** |
| TP2 | **−5%** |
| Leverage | **maks 5x** (di 5x kena SL ≈ −40% margin) |

> ⚠️ **Bukan saran finansial.** Trading futures pakai leverage bisa menghabiskan modal. DYOR.

## Filter & score

- Koin: Bybit USDT linear perpetual (crypto saja), **listing ≥ 30 hari**, **turnover 24j ≥ $5 juta**.
- Dicek **sekali per candle 1H tutup** (±60 detik setelah close).
- **Dedupe:** 1 alert per koin per candle. **Skip** kalau harga sudah bergerak > 3% dari close candle.
- Opsional batas jumlah alert per jam (`MAX_ALERTS_PER_HOUR`, default 0 = semua).
- **Score x/6** (makin tinggi makin kuat):
  1. EMA5 di atas EMA10 & EMA30
  2. Nukik turun pertama
  3. EMA10 < EMA30 (tren besar turun)
  4. Funding positif (long bayar short)
  5. Turnover 24j ≥ $20 juta
  6. Harga di bawah EMA30 4H

## Hasil backtest (ringkas)

1 tahun, 10 koin besar, 1H: **TP −5% / SL +8% → WR 68%, +$344** (entry acak dengan exit sama: +$214).
**TP −3% → WR 78%, +$273.** Detail + catatan jujur di [RESULTS.md](RESULTS.md).
Intinya: WR tinggi sebagian besar karena exit + market lagi downtrend; long di setup ini rugi.

## Install

Butuh **Python 3.9+**. Bot-nya cuma pakai standard library — tidak perlu `pip install`.

### Linux / VPS
```bash
git clone https://github.com/Corazontrafa06/ema5-top-curl-short-bot.git
cd ema5-top-curl-short-bot
cp .env.example .env        # opsional: isi Telegram / webhook
python3 bot.py --once       # tes: cek candle 1H terakhir, cetak hasil (tidak kirim)
python3 bot.py              # jalan terus
```
Biar tetap jalan setelah logout: `nohup python3 -u bot.py >> bot.log 2>&1 &`
atau pakai `tmux` / `screen`.

### Windows
1. Install Python dari python.org (centang "Add Python to PATH").
2. Download repo ini (Code → Download ZIP) lalu extract.
3. Di folder itu, copy `.env.example` jadi `.env` (opsional).
4. Buka Command Prompt di folder itu:
```bat
python bot.py --once
python bot.py
```

### systemd (VPS, auto-start saat reboot)
Lihat [`deploy/ema5bot.service`](deploy/ema5bot.service):
```bash
sudo cp deploy/ema5bot.service /etc/systemd/system/
sudo nano /etc/systemd/system/ema5bot.service   # sesuaikan User & WorkingDirectory
sudo systemctl daemon-reload
sudo systemctl enable --now ema5bot
journalctl -u ema5bot -f
```

## Output alert

- **Console** (selalu).
- **Telegram** (opsional): isi `TELEGRAM_BOT_TOKEN` (dari @BotFather) dan `TELEGRAM_CHAT_ID`.
- **Webhook** (opsional): isi `WEBHOOK_URL` → bot POST JSON per sinyal (ada field `message`).

Contoh:
```
🔻 EVAAUSDT SHORT — EMA5 top-curl 1H | score 4/6
Entry 1.647 | SL 1.77876 (+8%) | TP1 1.59759 (−3%) | TP2 1.56465 (−5%)
Candle 1H tutup 03:00 WIB: EMA5 ... > EMA10 ... & EMA30 ..., baru nukik turun. ...
Maks 5x, pasang SL langsung (di 5x kena SL ≈ −40% margin). Alert saja, bukan saran finansial.
```

## Konfigurasi (`.env`)

Semua variabel ada di [`.env.example`](.env.example): filter turnover/umur, `LATE_PCT`, SL/TP,
leverage, batas alert, zona waktu (default WIB, UTC+7). **Jangan pernah commit file `.env`.**

## Menjalankan ulang backtest

```bash
pip install -r requirements.txt
cd backtest
python fetch.py          # data 4H (dipakai bt.py untuk window waktu)
python fetch_tf.py       # data 1H & 2H
python mtf.py            # semua variasi TF / rule / SL / TP
python mtf_analyze.py    # ranking + perbandingan entry acak
```
`bt.py` = backtest SMA5 curl 4H (aturan awal), `ema_top.py` / `ema_top_analyze.py` = versi EMA 4H.
Data CSV dan file `.pkl` tidak di-commit; dibuat ulang oleh script di atas.

## Lisensi

MIT — lihat [LICENSE](LICENSE). Bukan saran finansial; gunakan dengan risiko sendiri.
