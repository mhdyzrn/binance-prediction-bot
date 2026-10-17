# Binance Prediction Trading Bot

Bot trading otomatis untuk pasar prediksi Binance menggunakan Python.

## Fitur Utama

- **Live Market Data:** Menggunakan feed resmi Binance Vision yang tahan blokir ISP Indonesia.
- **Signal Engine Berbasis Probabilitas & RSI:** Menghitung fair probability vs harga share orderbook untuk menemukan harga diskon (*mispriced outcome*).
- **Strategi Maker (0% Fee):** Selalu memasang Limit Order agar tidak terkena fee taker.
- **Early Take-Profit:** Menjual share sebelum ronde selesai jika harga sudah naik signifikan (+50%) untuk mengunci profit instan.
- **Paper Trading / Mode Simulasi:** Siap diuji langsung dengan saldo virtual $50 tanpa resiko uang sungguhan.
- **Interactive Dashboard:** Menampilkan ronde aktif, harga spot live BTC/USDT, strike target, orderbook, posisi terbuka, dan histori profit/loss.

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
