# Binance Prediction Trading Bot

Bot trading otomatis untuk pasar prediksi Binance menggunakan Python.

## Fitur Utama (V3.0 Fully Validated Real Execution Edition)

- **Official Bundle Specification Compliance:** Mengirimkan parameter resmi `fundingSource: "MPC"` dan `accountType: "SPOT"` dengan validasi `timeInForce: "FOK"` sesuai spesifikasi resmi Binance SAPI `place-order-bundle` (terverifikasi 100% order real berhasil on-chain).
- **Isolated Real & Simulation Histories:** Pemisahan total berkas riwayat transaksi dan statistik performa sesi (`real_trade_history.json` untuk trading riil dan `trade_history.json` untuk simulasi). Net PnL dan Win Rate pada mode Real murni menampilkan performa riil tanpa tercampur hasil simulasi.
- **SAS (Secure Auto-Signing) Detector:** Mendeteksi status aktivasi Secure Auto-Signing (SAS) akun Binance Web3 secara otomatis saat bot mulai berjalan dan memandu pengguna.
- **Order Book Liquidity Guard:** Mencegah taruhan pada probabilitas ekstrem (>92% / Payout < 1.08x) di mana buku pesanan Predict.fun/Binance kehabisan penjual, sehingga tidak terkena error *lack of liquidity*.
- **Safe Sniper Execution Window:** Mengamankan jendela eksekusi taruhan di rentang 75 detik hingga 25 detik sebelum kedaluwarsa (`SNIPER_DEADLINE_SECONDS=25`), menghindari zona penutupan likuiditas menjelang akhir ronde.
- **Dynamic 20% Slippage Protection:** Toleransi slippage 2000 bps (20%) untuk eksekusi cepat saat fluktuasi harga tanpa slippage rejection.
- **Dual-Wallet Balance Detection:** Mendeteksi saldo riil secara otomatis baik dari **Binance Web3 Prediction Wallet** (`walletBalance`) maupun **Spot Wallet** (CEX USDT free).
- **Auto Funding Source Routing:** Otomatis menyesuaikan sumber pembayaran tiket taruhan (`WALLET` atau `CEX`) sesuai ketersediaan saldo di akun.
- **Auto-Claim Winnings (Batch-Redeem):** Otomatis mengklaim hasil hadiah ronde yang menang langsung ke saldo Prediction Wallet Anda.
- **Dynamic Volatility Delta & Order Book Pricing:** Menghitung probabilitas dan payout Naik/Turun secara dinamis menggunakan model volatilitas pasar biner dan sisa waktu ronde. Angka persentase dan estimasi payout sinkron dan realistis mengikuti pergerakan buku order (*Web3 Order Book*) aplikasi Binance asli.
- **Auto-Compounding & Step-Down Rule (Max $2):** Ukuran taruhan membesar otomatis secara bertingkat seiring bertambahnya saldo ($10+ ➔ $1, $50+ ➔ Max $2 USDT), dan otomatis turun (*step-down*) jika saldo mengalami penurunan demi melindungi modal dari drawdown.
- **Presisi Strike 5M Open:** Mengambil harga pembukaan (*open price*) candlestick 5M resmi Binance Vision agar strike price 100% akurat meski bot dinyalakan di tengah ronde.
- **Strict Sniper Filter (Anti-Noise):** Mencegah taruhan spekulatif jika selisih harga < $15 demi menjaga winrate dan modal kecil ($10).
- **Native RSI-14 Momentum Guard:** Mengukur momentum 1-menit secara native untuk menolak sinyal beli di kondisi jenuh (*overbought/oversold*).
- **Saldo Simulasi Persisten ($10):** Saldo tersimpan otomatis ke `sim_balance.json` dan tidak di-reset saat restart kecuali jika saldo habis.
- **Proteksi Kekalahan Beruntun (Cooldown):** Jeda otomatis 1 ronde jika terjadi 2 kekalahan beruntun untuk melindungi saldo dari market choppy/abnormal.
- **Log Histori Permanen:** Hasil trading tersimpan otomatis di `trade_history.json` untuk pengujian 24 jam tanpa kehilangan data saat bot dimatikan.
- **Adaptive Polling:** Polling cepat (1 detik) di zona sniper (<75s) dan hemat baterai (2 detik) di zona observasi santai (>75s) khusus Termux HP.
- **Interactive Dashboard:** Menampilkan level Auto-Compound, ronde aktif, harga spot live, strike 5M open, RSI-14, format USDT, Net PnL, Win Rate, dan notifikasi filter sinyal.


## Cara Menjalankan

Masuk ke folder bot dan jalankan:

```bash
cd ~/binance-prediction-bot
pip install -r requirements.txt
python3 bot.py
```

## Pengaturan (config.py atau .env)

Secara default, bot berjalan dalam **Mode Simulasi (Paper Trading)** dengan modal taruhan **$1.00** per ronde.

Jika ingin beralih ke akun live Binance:
1. Salin `.env.example` menjadi `.env`:
   ```bash
   cp .env.example .env
   ```
2. Isi `BINANCE_API_KEY` dan `BINANCE_API_SECRET`. Pastikan API Key di Binance sudah dicentang izin **[Prediction Trading]**.
3. Ubah `SIMULATION_MODE = False` di `config.py` atau di `.env`.
