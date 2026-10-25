import os
from typing import Dict, Any

def load_env_file(filepath: str = ".env") -> None:
    """Memuat environment variables dari file .env secara mandiri tanpa library eksternal"""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'").strip('"')
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

# Muat dari .env lokal
load_env_file()
load_env_file(os.path.join(os.path.dirname(__file__), ".env"))

# -------------------------------------------------------------
# MODE OPERASI & KEAMANAN
# -------------------------------------------------------------
# Aplikasi Futures hanya mengizinkan SIGNAL_ONLY sampai executor tersedia.
TRADING_MODE = os.getenv("TRADING_MODE", "SIGNAL_ONLY").upper()

# Kept for compatibility; LIVE is currently rejected by the Futures application.
ENABLE_LIVE_TRADING = os.getenv("ENABLE_LIVE_TRADING", "false").lower() == "true"

# Kredensial Binance API
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

# Endpoint Binance Futures USDT-M
FUTURES_MAINNET_URL = "https://fapi.binance.com"
FUTURES_TESTNET_URL = "https://testnet.binancefuture.com"
BASE_URL = FUTURES_TESTNET_URL if (BINANCE_TESTNET and TRADING_MODE == "TESTNET") else FUTURES_MAINNET_URL

# -------------------------------------------------------------
# SPESIFIKASI PASAR & PREDIKSI
# -------------------------------------------------------------
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
ANALYSIS_TIMEFRAME = "1m"         # Candle 1 menit untuk analisis indikator
PREDICTION_HORIZON_MINUTES = 5     # Horizon evaluasi 5 menit (5 candle berikutnya)

# -------------------------------------------------------------
# PARAMETER STRATEGI KUANTITATIF
# -------------------------------------------------------------
# A. Trend Filter (EMA 20 & EMA 50)
EMA_FAST_PERIOD = int(os.getenv("EMA_FAST_PERIOD", "20"))
EMA_SLOW_PERIOD = int(os.getenv("EMA_SLOW_PERIOD", "50"))
EMA_SIDEWAYS_THRESHOLD = float(os.getenv("EMA_SIDEWAYS_THRESHOLD", "8.0"))  # Jarak minimal EMA20-EMA50 ($8)

# B. Momentum Filter (RSI 14)
RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
RSI_BUY_MIN = float(os.getenv("RSI_BUY_MIN", "50.0"))
RSI_BUY_MAX = float(os.getenv("RSI_BUY_MAX", "75.0"))
RSI_SELL_MIN = float(os.getenv("RSI_SELL_MIN", "25.0"))
RSI_SELL_MAX = float(os.getenv("RSI_SELL_MAX", "50.0"))

# C. Liquidity Sweep Detection (Swing High / Low 20 candle)
SWING_LOOKBACK = int(os.getenv("SWING_LOOKBACK", "20"))

# D. Volume Confirmation
VOLUME_LOOKBACK = int(os.getenv("VOLUME_LOOKBACK", "20"))
ENABLE_VOLUME_FILTER = os.getenv("ENABLE_VOLUME_FILTER", "true").lower() == "true"

# E. ATR & Volatility Filter
ATR_PERIOD = int(os.getenv("ATR_PERIOD", "14"))
MIN_ATR_THRESHOLD = float(os.getenv("MIN_ATR_THRESHOLD", "15.0"))  # Volatilitas minimal ($15 per candle)

# F. Filter Candle Ekstrem & Spread
MAX_CANDLE_BODY_ATR_MULT = float(os.getenv("MAX_CANDLE_BODY_ATR_MULT", "2.5"))  # Hindari entry jika candle melompat > 2.5x ATR
MAX_SPREAD_USDT = float(os.getenv("MAX_SPREAD_USDT", "5.0"))                   # Toleransi spread bid-ask

# G. Cooldown
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "5"))                     # Jeda 5 menit setelah entry

# H. Simulasi Paper Trading & Saldo Virtual
INITIAL_SIM_BALANCE = float(os.getenv("INITIAL_SIM_BALANCE", "100.0"))         # Saldo awal simulasi: $100.00 USDT
SIM_TRADE_SIZE_USDT = float(os.getenv("SIM_TRADE_SIZE_USDT", "10.0"))          # Ukuran per trade simulasi: $10.00 USDT
SIM_BALANCE_FILE = "sim_balance.json"

# -------------------------------------------------------------
# MANAJEMEN RISIKO & BIAYA TRANSAKSI FUTURES
# -------------------------------------------------------------
DEFAULT_LEVERAGE = int(os.getenv("DEFAULT_LEVERAGE", "3"))                     # Leverage rendah (3x)
RISK_PER_TRADE_PERCENT = float(os.getenv("RISK_PER_TRADE_PERCENT", "1.0"))     # Maks 1% risiko modal per trade
TAKER_FEE_RATE = float(os.getenv("TAKER_FEE_RATE", "0.0005"))                  # Fee taker Binance Futures 0.05%
MAKER_FEE_RATE = float(os.getenv("MAKER_FEE_RATE", "0.0002"))                  # Fee maker 0.02%
SLIPPAGE_RATE = float(os.getenv("SLIPPAGE_RATE", "0.0002"))                    # Estimasi slippage 0.02%
STOP_LOSS_ATR_MULT = float(os.getenv("STOP_LOSS_ATR_MULT", "1.5"))             # SL 1.5x ATR
TAKE_PROFIT_ATR_MULT = float(os.getenv("TAKE_PROFIT_ATR_MULT", "2.0"))         # TP 2.0x ATR
MAX_ACTIVE_POSITIONS = 1
KILL_SWITCH_DRAWDOWN = 0.10                                                    # Matikan bot jika drawdown > 10%

def get_summary_dict() -> Dict[str, Any]:
    """Mengembalikan ringkasan konfigurasi sistem aktif"""
    return {
        "symbol": SYMBOL,
        "mode": TRADING_MODE,
        "base_url": BASE_URL,
        "analysis_timeframe": ANALYSIS_TIMEFRAME,
        "horizon_minutes": PREDICTION_HORIZON_MINUTES,
        "ema_fast": EMA_FAST_PERIOD,
        "ema_slow": EMA_SLOW_PERIOD,
        "rsi_period": RSI_PERIOD,
        "atr_period": ATR_PERIOD,
        "min_atr": MIN_ATR_THRESHOLD,
        "volume_filter": ENABLE_VOLUME_FILTER,
        "leverage": DEFAULT_LEVERAGE
    }
