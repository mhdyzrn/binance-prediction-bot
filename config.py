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

# Sumber Dana Taruhan Real (Pilihan: AUTO, WALLET, CEX)
# WALLET = Binance Web3 Prediction Wallet
# CEX    = Binance Spot Wallet
# AUTO   = Otomatis gunakan wallet yang memiliki saldo USDT
FUNDING_SOURCE = os.getenv("FUNDING_SOURCE", "AUTO").upper()

# Target Pasar: BTC (Bitcoin) 5 Menit
TARGET_ASSET = "BTC"                                # Nama tampilan
TARGET_SYMBOL = "BTCUSDT"                           # Pasangan pasar spot
ROUND_MINUTES = 5                                   # Durasi ronde 5 menit
BET_AMOUNT_USDT = float(os.getenv("BET_AMOUNT", "1.0"))  # Nominal taruhan dasar (default 1 USDT)
INITIAL_VIRTUAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "10.0"))  # Saldo awal simulasi: $10.0
SIM_BALANCE_FILE = "sim_balance.json"                 # File penyimpan saldo simulasi agar tidak ter-reset

# ==========================================================
# SISTEM AUTO-COMPOUNDING TIERED & STEP-DOWN RULE (MAX $2)
# ==========================================================
ENABLE_AUTO_COMPOUND = os.getenv("ENABLE_AUTO_COMPOUND", "True").lower() == "true"
MAX_COMPOUND_BET = float(os.getenv("MAX_COMPOUND_BET", "2.0"))  # Batas maksimal taruhan: $2.00 USDT

# Skema Level Compounding:
# Tier 1: Saldo < $50.00    ➔ Bet $1.00 USDT
# Tier 2: Saldo >= $50.00   ➔ Bet $2.00 USDT (Batas Maksimal Terkunci $2)
# Step-Down Rule: Jika saldo turun di bawah batas tier, taruhan otomatis turun (step-down) ke tier sebelumnya
COMPOUND_TIERS = [
    (50.0,  2.0, "Tier 2 ($50+ Max $2)"),
    (0.0,   1.0, "Tier 1 ($10+)"),
]


def calculate_compound_bet(balance: float) -> tuple[float, str]:
    """
    Menghitung ukuran taruhan dinamis berdasarkan saldo saat ini.
    Maksimal taruhan dibatasi $2.00 USDT (atau MAX_COMPOUND_BET).
    Menerapkan Step-Down Rule secara otomatis:
    - Jika saldo naik melewati batas tier -> taruhan naik ke tier berikutnya.
    - Jika saldo turun di bawah batas tier -> taruhan otomatis turun (step-down)
      untuk melindungi modal dari drawdown.
    """
    if not ENABLE_AUTO_COMPOUND:
        return min(BET_AMOUNT_USDT, MAX_COMPOUND_BET), "Fixed"

    for min_bal, bet_amt, tier_name in COMPOUND_TIERS:
        if balance >= min_bal:
            capped_bet = min(bet_amt, MAX_COMPOUND_BET)
            actual_bet = min(capped_bet, balance) if balance > 0 else capped_bet
            return actual_bet, tier_name

    return min(BET_AMOUNT_USDT, MAX_COMPOUND_BET), "Tier 1 ($10+)"


# Parameter Strategi Late-Sniper (BTC 5 Menit)
# Eksekusi dilakukan di jendela sniper aman sebelum kedaluwarsa
SNIPER_TRIGGER_SECONDS = int(os.getenv("SNIPER_TRIGGER_SECONDS", "75"))    # Jendela eksekusi mulai: sisa 75 detik (01:15)
SNIPER_DEADLINE_SECONDS = int(os.getenv("SNIPER_DEADLINE_SECONDS", "25"))  # Batas akhir aman: sisa 25 detik (mencegah order book kosong/lack of liquidity)
SNIPER_MIN_DIFF = float(os.getenv("SNIPER_MIN_DIFF", "15.0"))              # Minimal selisih harga BTC ($15) untuk menghindari noise
MIN_PAYOUT_MULTIPLIER = float(os.getenv("MIN_PAYOUT_MULTIPLIER", "1.08"))  # Minimal payout 1.08x (menghindari probabilitas >92% yang kering likuiditas)
SLIPPAGE_BPS = int(os.getenv("SLIPPAGE_BPS", "2000"))                      # Toleransi slippage: default 20% (2000 basis points)

# Parameter Indikator RSI (1M timeframe)
RSI_PERIOD = 14                                       # Periode RSI 14
RSI_OVERBOUGHT = 78.0                                 # Tahan sinyal NAIK jika RSI > 78 (rawan pembalikan turun)
RSI_OVERSOLD = 22.0                                   # Tahan sinyal TURUN jika RSI < 22 (rawan pantulan naik)

# Proteksi Kekalahan Beruntun (Cooldown untuk pengujian 24 Jam)
# Catatan: Daily Stop-Loss dan Daily Take-Profit dinonaktifkan sesuai permintaan pengujian 24 jam
MAX_CONSECUTIVE_LOSS = 2                              # Jika 2x loss beruntun, jeda 1 ronde untuk hindari market liar
COOLDOWN_ROUNDS = 1                                   # Jumlah ronde istirahat saat cooldown aktif (1 ronde = 5 menit)

# Penyimpanan Histori Transaksi Permanen Terpisah (Real vs Simulasi)
SIM_HISTORY_FILE = "trade_history.json"                   # Riwayat transaksi simulasi
REAL_HISTORY_FILE = "real_trade_history.json"             # Riwayat transaksi real live
HISTORY_FILE = REAL_HISTORY_FILE if not SIMULATION_MODE else SIM_HISTORY_FILE
LOOP_INTERVAL_SECONDS = 1                             # Refresh rate interval dasar

