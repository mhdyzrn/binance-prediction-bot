import os

# Fungsi pemuat file .env mandiri (tanpa perlu install library tambahan)
def load_env(filepath=".env"):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    k = key.strip()
                    if k not in os.environ:
                        os.environ[k] = val.strip().strip("'").strip('"')

# Muat variabel dari .env
load_env()

# Mode Trading:
# Set ke False untuk REAL / LIVE TRADING menggunakan saldo asli Binance
# Set ke True untuk simulasi latihan
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "False").lower() == "true"

# Binance API Credentials (Wajib diisi di file .env jika mode REAL)
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Endpoint Binance
# Base URL untuk transaksi SAPI/API riil
BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")

# Mirror data pasar resmi Binance (Anti-blokir ISP di Indonesia)
BINANCE_VISION_URL = "https://data-api.binance.vision"

# Proxy Statis (Opsional: berguna untuk IP Whitelist Binance tetap & anti-blokir di Termux)
BINANCE_PROXY = os.getenv("BINANCE_PROXY", "")

# Target Pasar: BTC (Bitcoin) 5 Menit
TARGET_ASSET = "BTC"                                # Nama tampilan
TARGET_SYMBOL = "BTCUSDT"                           # Pasangan pasar spot
ROUND_MINUTES = 5                                   # Durasi ronde 5 menit
BET_AMOUNT_USDT = float(os.getenv("BET_AMOUNT", "1.0"))  # Nominal taruhan (default 1 USDT)
INITIAL_VIRTUAL_BALANCE = 50.0                      # Saldo awal simulasi (jika mode simulasi)

# Parameter Strategi Late-Sniper (BTC 5 Menit)
# Eksekusi dilakukan di sisa 75 detik terakhir sebelum kedaluwarsa
SNIPER_TRIGGER_SECONDS = int(os.getenv("SNIPER_TRIGGER_SECONDS", "75"))    # Jendela eksekusi: sisa 75 detik (01:15)
SNIPER_DEADLINE_SECONDS = int(os.getenv("SNIPER_DEADLINE_SECONDS", "10"))  # Batas akhir: sisa 10 detik (00:10)
SNIPER_MIN_DIFF = float(os.getenv("SNIPER_MIN_DIFF", "15.0"))              # Minimal selisih harga BTC ($15) untuk menghindari noise

# Parameter Indikator RSI (1M timeframe)
RSI_PERIOD = 14                                       # Periode RSI 14
RSI_OVERBOUGHT = 78.0                                 # Tahan sinyal NAIK jika RSI > 78 (rawan pembalikan turun)
RSI_OVERSOLD = 22.0                                   # Tahan sinyal TURUN jika RSI < 22 (rawan pantulan naik)

# Proteksi Kekalahan Beruntun (Cooldown untuk pengujian 24 Jam)
# Catatan: Daily Stop-Loss dan Daily Take-Profit dinonaktifkan sesuai permintaan pengujian 24 jam
MAX_CONSECUTIVE_LOSS = 2                              # Jika 2x loss beruntun, jeda 1 ronde untuk hindari market liar
COOLDOWN_ROUNDS = 1                                   # Jumlah ronde istirahat saat cooldown aktif (1 ronde = 5 menit)

# Penyimpanan Histori Transaksi Permanen
HISTORY_FILE = "trade_history.json"                   # Lokasi file riwayat transaksi
LOOP_INTERVAL_SECONDS = 1                             # Refresh rate interval dasar

