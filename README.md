# Binance Prediction Trading Bot

Bot trading otomatis untuk pasar prediksi Binance menggunakan Python.

## Fitur Utama (V4.0 Clear Payout & Profit Breakdown Dashboard)

- **Transparent Payout & Profit Breakdown:** Memperjelas tampilan target payout pada dashboard aktif dengan memisahkan modal awal dan keuntungan bersih secara eksplisit (contoh: `Target Payout : 1.10 USDT (Modal $1.00 + Untung +$0.10)`), sehingga pengguna memahami dengan pasti berapa saldo yang akan masuk ke dompet jika menang.
- **Real Web3 Order Book Quotation:** Mengganti estimasi matematis teoritis dengan pembacaan langsung harga buku pesanan (*Web3 Order Book*) dan peluang resmi (`chance` & `price`) dari pasar Binance Web3 Prediction. Angka probabilitas dan multiplier payout di dashboard kini sama persis dengan yang tampil di aplikasi Binance.
- **Accurate Pre-Order & Post-Order Payout (`get-quote` Sync):** Menyelaraskan nilai `potential_win` (*Target Payout*) secara presisi dari kuotasi on-chain (`amountOut`) Binance SAPI. Menghilangkan 100% selisih antara estimasi (seperti 1.35x) dengan perolehan riil yang didapatkan akun (1.10x).
- **Drift-Free Precision Countdown (`next_tick` Scheduler):** Menghilangkan 100% masalah loncat detik (seperti dari 12 langsung ke 10). Tampilan hitung mundur kini berdetak presisi tepat 1.000 detik persis sesuai detik jam dinding secara berurutan dan mulus (*12 ➔ 11 ➔ 10 ➔ 09*).
- **Asynchronous Background Market Poller:** Memindahkan pengambilan data harga spot BTC, indikator RSI, pembaruan strike, dan status verifikasi settlement ke thread latar belakang terpisah (`daemon thread`). Pembaruan status pasar di terminal kini berjalan instan (< 1 ms) tanpa pernah tersendat oleh latensi jaringan API Binance.
- **100% Binance Web3 Prediction Lifecycle Alignment:** Seluruh tahapan trading bot diselaraskan secara penuh dengan siklus hidup resmi pasar prediksi Binance (Predict.fun di BNB Chain):
  1. *Fase Strike Snapshot:* Mengambil harga pembukaan resmi Chainlink Oracle (`variantData.startPrice`) langsung dari pasar Web3.
  2. *Fase Sniper Window (01:15 - 00:25):* Mengeksekusi order saat tren lilin 5M telah terbentuk 80-90% dan buku pesanan Binance masih memiliki likuiditas penuh.
  3. *Fase Penutupan Jendela (00:25 - 00:00):* Menghentikan order baru untuk menghindari penolakan *lack of liquidity* akibat penutupan order book oleh Binance.
  4. *Fase On-Chain Finalization (00:00 - 00:35):* Posisi dialihkan ke antrean verifikasi on-chain dan menunggu hasil resmi Chainlink Oracle selesai dicatat di blockchain BNB Chain tanpa evaluasi terburu-buru.
  5. *Fase Auto-Redeem & Reconciliation:* Klaim hadiah pemenang secara otomatis via `batch-redeem` on-chain dan mencatat keuntungan/kerugian riil identik dengan aplikasi Binance.
- **Extended Settlement Timeout (240 Detik):** Memperpanjang toleransi tunggu penyelesaian on-chain menjadi 4 menit (240 detik), memastikan bot tidak pernah melakukan fallback harga spot lokal saat jaringan blockchain mengalami kepadatan.
- **Loop Sleep & CPU Optimization (Termux Friendly):** Memperbaiki penempatan jeda perulangan (*adaptive sleep*) ke putaran utama bot (1s saat jendela sniper, 2s saat observasi santai). Mencegah loop tanpa jeda, menghemat daya baterai, konsumsi CPU, dan kuota data ponsel Android, serta menghindari limit request Binance API.
- **Double Betting Prevention & Active Position Recovery:** Mendeteksi posisi yang sedang berjalan di Binance SAPI saat startup atau reconnect. Posisi otomatis dipulihkan ke status aktif sehingga bot tidak akan pernah memasang taruhan ganda pada ronde yang sama.
- **Server Time Drift Auto-Sync & recvWindow 10000ms:** Menghitung selisih jam ponsel dengan server Binance secara otomatis saat booting dan memperlebar batas toleransi `recvWindow` ke 10.000 ms (10 detik), mencegah kegagalan order akibat error timestamp `-1021`.
- **Periodic On-Chain History Self-Healing:** Melakukan sinkronisasi riwayat transaksi secara otomatis setiap pergantian ronde 5 menit langsung dari endpoint resmi Binance SAPI, menjamin PnL, Win/Loss, dan saldo selalu 100% konsisten.
- **Strict Oracle Finalization Guard:** Menjamin posisi tidak akan pernah diselesaikan secara prematur di detik 00-01 saat Chainlink Oracle Binance masih dalam proses finalisasi on-chain (15–35 detik). Posisi tetap berada di antrean `pending_settlement` dengan indikator `⏳ VERIFIKASI SETTLEMENT ON-CHAIN` hingga status resmi berubah menjadi `PENDING_CLAIM`, `CLAIMED`, atau `SETTLED`.
- **Zero Premature Loss Resolution:** Mencegah bug di mana posisi menang terbaca sebagai *loss* karena pembacaan awal saat nilai `isWinner` / `finalOutcome` masih `null` di SAPI sebelum transaksi on-chain diverifikasi.
- **Official On-Chain Auto-Redeem (`batch-redeem`):** Memperbaiki parameter resmi Binance SAPI `batch-redeem` menggunakan signed query params sehingga hadiah kemenangan langsung di-klaim (*redeemed*) otomatis di blockchain dan langsung masuk ke saldo wallet USDT aktif.
- **Dual Settlement Pipeline (`position/filter` & `settled-history`):** Mendeteksi posisi pemenang secara instan via `position/filter` (`PENDING_CLAIM`) dan posisi kalah via `settled-history`, menghilangkan jeda fallback dan sinkron 100% dengan smart contract Binance.
- **Strict Position Re-Matching Guard:** Memastikan posisi lama yang sudah tercatat di riwayat tidak akan pernah dicocokkan ulang saat memeriksa status penyelesaian on-chain Binance SAPI.
- **Dynamic Market Name & Identity:** Menampilkan nama pasar prediksi dinamis pada dashboard utama, terminal startup, dan laporan sesi (contoh: *BTC Naik atau Turun dalam 5 Menit?*) yang menyesuaikan secara otomatis dengan aset dan durasi ronde aktif.
- **Official On-Chain Settlement Sync:** Pada mode Real, hasil Menang/Kalah (Win/Loss) diverifikasi langsung dari endpoint resmi Binance Web3 Prediction SAPI `GET /sapi/v1/w3w/wallet/prediction/position/settled-history`. Menghilangkan 100% selisih kalkulasi antara estimasi harga spot lokal dan hasil resolusi on-chain Chainlink Oracle Binance.
- **Chainlink Oracle Strike Price Integration:** Mengambil harga Strike resmi ronde (`variantData.startPrice`) langsung dari pasar Binance Web3 Prediction (`market/list`), bukan lagi sekadar estimasi candlestick spot Binance.
- **Asynchronous Settlement Pipeline:** Posisi yang baru saja selesai di detik 00 dialihkan ke antrean `pending_settlement` dan dipantau berkala (5-30 detik) hingga oracle on-chain Binance selesai melakukan penyelesaian (settlement). Dashboard menampilkan status `⏳ VERIFIKASI SETTLEMENT ON-CHAIN` secara transparan.
- **Zero-Discrepancy History & PnL:** Sinkronisasi otomatis riwayat transaksi riil saat bot dinyalakan. Total transaksi, Win/Loss, Net PnL, dan saldo dompet di Termux terverifikasi 100% identik dengan aplikasi Binance.
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
- **Presisi Strike 5M Open:** Mengambil harga pembukaan (*open price*) candlestick 5M resmi Binance Vision sebagai fallback jika data Web3 belum terbuka.
- **Strict Sniper Filter (Anti-Noise):** Mencegah taruhan spekulatif jika selisih harga < $15 demi menjaga winrate dan modal kecil ($10).
- **Native RSI-14 Momentum Guard:** Mengukur momentum 1-menit secara native untuk menolak sinyal beli di kondisi jenuh (*overbought/oversold*).
- **Saldo Simulasi Persisten ($10):** Saldo tersimpan otomatis ke `sim_balance.json` dan tidak di-reset saat restart kecuali jika saldo habis.
- **Proteksi Kekalahan Beruntun (Cooldown):** Jeda otomatis 1 ronde jika terjadi 2 kekalahan beruntun untuk melindungi saldo dari market choppy/abnormal.
- **Log Histori Permanen:** Hasil trading tersimpan otomatis di `real_trade_history.json` dan `trade_history.json`.
- **Adaptive Polling:** Polling cepat (1 detik) di zona sniper (<75s) dan hemat baterai (2 detik) di zona observasi santai (>75s) khusus Termux HP.
- **Interactive Dashboard:** Menampilkan level Auto-Compound, ronde aktif, harga spot live, strike Chainlink/5M open, RSI-14, format USDT, Net PnL, Win Rate, dan notifikasi filter sinyal.


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
