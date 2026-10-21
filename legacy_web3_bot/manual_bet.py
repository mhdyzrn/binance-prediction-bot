import sys
import time
import config
from binance_client import BinanceClient, PredictionEngine

def place_manual_order(direction: str, amount: float = None):
    """
    Eksekusi order manual Naik atau Turun secara langsung.
    Bekerja otomatis sesuai mode aktif di .env (REAL atau SIMULASI).
    """
    client = BinanceClient()
    engine = PredictionEngine(client)

    # Sinkronkan state pasar terkini
    market = engine.update_market_state()
    
    dir_formatted = "Naik" if direction.lower() in ["naik", "up", "bull", "buy"] else "Turun"
    bet_amt = amount if amount is not None else market.get("bet_amount", config.BET_AMOUNT_USDT)
    payout_mult = market["payout_naik"] if dir_formatted == "Naik" else market["payout_turun"]
    
    mode_str = "REAL LIVE" if engine.is_real else "SIMULASI"
    print(f"\n==========================================")
    print(f"       EKSEKUSI PREDIKSI MANUAL")
    print(f"==========================================")
    print(f"Mode          : {mode_str}")
    print(f"Arah Dipilih  : {dir_formatted.upper()}")
    print(f"Nominal       : {bet_amt:.2f} USDT")
    print(f"Spot BTC      : ${market['ref_price']:,.2f}")
    print(f"Strike Price  : ${market['strike_price']:,.2f}")
    print(f"Selisih       : {market['diff_str']}")
    print(f"Estimasi Odds : {payout_mult:.2f}x")
    print(f"Sisa Waktu    : {market['countdown_str']}")
    print(f"------------------------------------------")

    res = engine.place_order(direction=dir_formatted, amount_usdt=bet_amt, payout_multiplier=payout_mult)
    if res.get("success"):
        print(f"\033[92m✔ SUKSES: {res.get('msg')} ({bet_amt:.2f} USDT)\033[0m")
        print(f"Saldo Tersisa : {engine.get_balance():.2f} USDT\n")
        return True
    else:
        print(f"\033[91m✘ GAGAL: {res.get('msg')}\033[0m\n")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Penggunaan: python3 manual_bet.py <naik|turun> [nominal_usdt]")
        print("Contoh    : python3 manual_bet.py naik 1.0")
        print("Contoh    : python3 manual_bet.py turun 2.0")
        sys.exit(1)

    direction_input = sys.argv[1]
    amount_input = float(sys.argv[2]) if len(sys.argv) > 2 else None
    place_manual_order(direction_input, amount_input)
