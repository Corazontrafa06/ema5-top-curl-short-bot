# Ringkasan Backtest

Data: Bybit USDT perpetual, **1 tahun**, 10 koin besar (BTC, ETH, SOL, XRP, BNB, DOGE, ADA, AVAX, LINK, SUI).
Asumsi: $10 margin × 5x ($50 notional) per trade, fee 0.055% per sisi, slippage 0.05%, 1 posisi per koin,
hold maks 240 jam. Trade dihitung dari candle close sinyal. Script: `backtest/mtf.py` + `backtest/mtf_analyze.py`.

Aturan: EMA5 (kuning) di atas EMA10 (hijau) & EMA30 (ungu), lalu **short pada nukik turun pertama** (`top_curl_down`).

| Timeframe | SL | TP | Trades | Win rate | Net | Entry acak (exit sama) |
|---|---|---|---|---|---|---|
| **1H** | +8% | −5% | 698 | **68.1%** | **+$344** | WR 65.6%, +$214 |
| **1H** | +8% | −3% | 946 | **77.6%** | +$273 | WR 75.2%, +$158 |
| 1H | +5% | −3% | 1106 | 69.1% | +$232 | WR 66.2%, +$107 |
| 1H | +8% | −2% | 1168 | 83.6% | +$207 | WR 81.7%, +$91 |
| 2H | +8% | −2% | 768 | 82.8% | +$129 | WR 81.3%, +$54 |
| 3H | +8% | −2% | 586 | 84.0% | +$145 | WR 81.3%, +$40 |

Detail lengkap: `backtest/mtf_top_with_baseline_results.csv`.

## Catatan jujur
- **WR tinggi sebagian besar datang dari exit** (TP kecil, SL lebar) **dan market setahun ini yang lagi turun.**
  Short di waktu acak dengan TP/SL sama juga dapat WR ~66–82%. Sinyal EMA hanya menambah ~2–3% WR
  dan sekitar +$100–130 net dibanding acak.
- **Long saat EMA kuning di atas rugi** di semua timeframe — jangan dibalik jadi sinyal long.
- 1H paling bagus; 2H/3H/4H lebih lemah.
- Semua koin positif, paling bagus di alt (DOGE, ADA, AVAX, SUI); BTC/ETH/BNB lebih tipis.
- SL +8% di 5x = **−40% margin** sekali kena. Kalau market berubah jadi uptrend, edge kemungkinan hilang.
- Backtest ≠ hasil masa depan. **Bukan saran finansial.**
