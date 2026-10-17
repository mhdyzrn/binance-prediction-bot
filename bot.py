import time
import os
import sys
from datetime import datetime
import config
from binance_client import BinanceClient, PredictionEngine
from strategy import PredictionStrategy

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

class BinanceAppPredictionBot:
    def __init__(self):
        self.client = BinanceClient()
        self.engine = PredictionEngine(self.client)
        self.strategy = PredictionStrategy()
        self.spinner_idx = 0
        self.placed_expiries = set()

    def init_screen(self):
        sys.stdout.write("\033[2J\033[H\033[?25l")
        sys.stdout.flush()

    def restore_screen(self):
        sys.stdout.write("\033[?25h\033[0m\n")
        sys.stdout.flush()

    def render_dashboard(self, m: dict, signal: dict, spinner_char: str = "⠋", order_notice: str = ""):
        """
        Dashboard Terminal BTC 5 Menit:
        - Tampilan rapi, presisi 42 karakter (sangat pas untuk layar Termux HP)
        - Anti ghost text / anti teks bertumpuk menggunakan ANSI \\033[K
        - Warna kontras tinggi & indikator arah yang jelas
        """
        diff_val = m["diff_val"]
        if diff_val < 0:
            diff_colored = f"\033[1;91m{m['diff_str']}\033[0m (\033[37m${m['ref_price']:,.2f}\033[0m)"
        else:
            diff_colored = f"\033[1;92m{m['diff_str']}\033[0m (\033[37m${m['ref_price']:,.2f}\033[0m)"

        mode_badge = "\033[1;42;30m REAL 5M \033[0m" if self.engine.is_real else "\033[1;43;30m SIMULASI 5M \033[0m"

        positions = self.engine.active_positions
        active_pos = positions[-1] if positions else None

        history = self.engine.history
        total_trades = len(history)
        wins = sum(1 for h in history if h.get("won"))
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

        p_naik_str = f"Win {m['payout_naik']:.2f} U"
        p_turun_str = f"Win {m['payout_turun']:.2f} U"
        prob_naik_str = f"{m['prob_naik']}%"
        prob_turun_str = f"{m['prob_turun']}%"

        # Status Koneksi Jaringan
        is_online = m.get("is_online", True)
        stale_sec = m.get("stale_seconds", 0)
        if is_online:
            conn_badge = "\033[1;92m● ONLINE\033[0m"
        else:
            conn_badge = f"\033[1;91m● TERPUTUS ({stale_sec}s)\033[0m"

        lines = [
            " \033[1;36m══════════════════════════════════════════\033[0m",
            f"  \033[1;37mBINANCE PREDICTION\033[0m   {mode_badge}",
            " \033[1;36m══════════════════════════════════════════\033[0m",
            f"  Status Jaringan : {conn_badge}",
            f"  Kedaluwarsa     : \033[1m{m['expiry_str']}\033[0m",
            f"  Harga Strike    : \033[1;37m${m['strike_price']:,.2f}\033[0m",
            f"  Harga Spot      : {diff_colored}",
            f"  Hitung Mundur   : \033[1;93m{m['countdown_str']}\033[0m \033[96m{spinner_char}\033[0m",
            " ──────────────────────────────────────────",
            "  ┌──────────────────┐  ┌──────────────────┐",
            "  │      \033[1;92m▲ NAIK\033[0m      │  │     \033[1;91m▼ TURUN\033[0m      │",
            f"  │{prob_naik_str:^18}│  │{prob_turun_str:^18}│",
            f"  │{p_naik_str:^18}│  │{p_turun_str:^18}│",
            "  └──────────────────┘  └──────────────────┘",
            " ──────────────────────────────────────────",
            f"  Saldo Akun      : \033[1;32m{m['balance_usdt']:.2f} USDT\033[0m (Bet: {config.BET_AMOUNT_USDT:.2f} U)",
        ]

        # Status Posisi & Sinyal Late-Sniper
        if active_pos:
            arrow = "▲" if active_pos["direction"] == "Naik" else "▼"
            dir_color = "\033[1;92m" if active_pos["direction"] == "Naik" else "\033[1;91m"
            tag = "REAL" if active_pos.get("is_real") else "SIM"
            lines.append(f"  Posisi Aktif    : {dir_color}{arrow} {active_pos['direction'].upper()}\033[0m ({config.BET_AMOUNT_USDT:.2f} U) [{tag}]")
            lines.append(f"  Target Payout   : \033[1;93m+{active_pos['potential_win']:.2f} USDT\033[0m")
            lines.append("  Status Bot      : \033[92m✔ Order Sukses! Menunggu expiry...\033[0m")
        else:
            if not is_online:
                lines.append(f"  Status Bot      : \033[1;91m⚠ Jaringan Terputus! Reconnecting...\033[0m")
            elif signal["action"] == "OBSERVE":
                pred = "▲ NAIK" if m["diff_val"] >= 0 else "▼ TURUN"
                pred_col = "\033[1;92m" if m["diff_val"] >= 0 else "\033[1;91m"
                lines.append(f"  Kecenderungan   : {pred_col}{pred}\033[0m (Sniper di 01:15)")
                lines.append(f"  Status Bot      : \033[90m{spinner_char} {signal['reason']}\033[0m")
            elif signal["action"] == "EXPIRED_SOON":
                lines.append("  Sinyal Sniper   : \033[1;91m⛔ Jendela Taruhan Ditutup\033[0m")
                lines.append(f"  Status Bot      : \033[90m{spinner_char} {signal['reason']}\033[0m")
            else:
                target_dir = signal.get("direction", "Naik")
                dir_col = "\033[1;92m" if target_dir == "Naik" else "\033[1;91m"
                arrow = "▲" if target_dir == "Naik" else "▼"
                lines.append(f"  Sinyal Sniper   : \033[1;33m🎯 JENDELA TERBUKA ➔\033[0m {dir_col}{arrow} {target_dir.upper()}\033[0m")
                lines.append(f"  Status Bot      : \033[96m{spinner_char} Memasang posisi {target_dir}...\033[0m")

        if order_notice:
            lines.append(f"  Notifikasi      : {order_notice}")

        if history:
            last = history[-1]
            h_stat = "\033[1;92mWIN\033[0m" if last["won"] else "\033[1;91mLOSS\033[0m"
            p_sign = "+" if last["profit"] >= 0 else ""
            lines.append(" ──────────────────────────────────────────")
            lines.append(f"  Ronde Terakhir  : [{last['round']}] {last['direction'].upper()} ➔ {h_stat} ({p_sign}{last['profit']:.2f} U)")
            lines.append(f"  Performa Bot    : \033[1;37m{wins}/{total_trades}\033[0m Menang (\033[1;93m{win_rate:.0f}%\033[0m)")

        lines.append(" ──────────────────────────────────────────")
        lines.append("  \033[90m[Ctrl+C] Hentikan Bot\033[0m")

        # Setiap baris diakhiri dengan \033[K (clear to end of line) agar tidak ada sisa karakter
        content = "\n".join(f"{line}\033[K" for line in lines)
        sys.stdout.write(f"\033[H{content}\n\033[J")
        sys.stdout.flush()

    def check_prerequisites(self):
        """Memeriksa kesiapan koneksi dan kredensial API"""
        print("=" * 55)
        print("   BINANCE PREDICTION BOT - BTC 5 MENIT (REAL & SIM)  ")
        print("=" * 55)
        
        # Test koneksi data pasar dengan retry otomatis (hingga 3 kali)
        btc_price = None
        for attempt in range(1, 4):
            try:
                if attempt > 1:
                    print(f"Menghubungkan ulang ke feed pasar Binance (Percobaan {attempt}/3)...")
                btc_price = self.client.get_spot_price()
                print(f"✔ Feed Harga BTC/USDT Terhubung: ${btc_price:,.2f}")
                break
            except Exception as e:
                print(f"  ⚠ Percobaan {attempt} gagal: {e}")
                if attempt < 3:
                    time.sleep(2)

        if btc_price is None:
            print("\n\033[91m✘ Gagal terhubung ke feed pasar Binance setelah 3 percobaan.\033[0m")
            print("Pastikan koneksi internet ponsel aktif atau VPN/Proxy berfungsi.")
            sys.exit(1)

        # Cek status mode Real Trading
        if self.engine.is_real:
            print("\033[1;92mMode Terpilih: REAL / LIVE TRADING\033[0m")
            if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
                print("\n\033[91m[PERINGATAN] API Key & Secret belum terpasang di file .env!\033[0m")
                print("Silakan edit file `.env` di folder bot dan isi:")
                print("  BINANCE_API_KEY=api_key_anda")
                print("  BINANCE_API_SECRET=api_secret_anda")
                print("\nBeralih otomatis sementara ke Mode Simulasi demi keamanan...")
                self.engine.is_real = False
                time.sleep(3)
            else:
                print("Memeriksa koneksi ke akun Binance...")
                success, msg, real_bal = self.client.test_account_connection()
                if success:
                    self.engine.cached_real_balance = real_bal
                    self.engine.last_balance_check = time.time()
                    print(f"✔ Akun Binance Terhubung! Saldo USDT Tersedia: {real_bal:.2f} USDT")
                    time.sleep(1.5)
                else:
                    print(f"\n\033[91m✘ Gagal terhubung ke Akun Binance:\033[0m {msg}")
                    print("\n\033[93m[Panduan Solusi]:\033[0m")
                    print("  1. Di Indonesia, domain `api.binance.com` diblokir oleh Kominfo/ISP.")
                    print("     Aktifkan VPN di HP Anda (misalnya Cloudflare 1.1.1.1 WARP atau Intra).")
                    print("  2. Atau jalankan Mode Simulasi (Paper Trading) dengan mengubah `.env`:")
                    print("     SIMULATION_MODE=True\n")
                    sys.exit(1)
        else:
            print("\033[1;93mMode Terpilih: SIMULASI (Paper Trading)\033[0m")
            print(f"Saldo Virtual Awal: {self.engine.get_balance():.2f} USDT")
            time.sleep(1.0)

    def run(self):
        self.check_prerequisites()
        self.init_screen()
        order_notice = ""
        last_expiry_id = None

        try:
            while True:
                try:
                    # 1. Update status pasar
                    market = self.engine.update_market_state()
                    expiry_id = market["expiry_str"]

                    # Bersihkan notifikasi jika masuk ronde baru
                    if last_expiry_id and last_expiry_id != expiry_id:
                        order_notice = ""
                    last_expiry_id = expiry_id

                    # 2. Evaluasi strategi Late-Sniper
                    signal = self.strategy.evaluate_signal(market)

                    if expiry_id not in self.placed_expiries and signal["action"] == "ENTER":
                        direction = signal["direction"]
                        payout_mult = market["payout_naik"] if direction == "Naik" else market["payout_turun"]
                        
                        res = self.engine.place_order(
                            direction=direction,
                            amount_usdt=config.BET_AMOUNT_USDT,
                            payout_multiplier=payout_mult
                        )
                        
                        if res.get("success"):
                            self.placed_expiries.add(expiry_id)
                            order_notice = f"\033[92m✔ {res.get('msg')}\033[0m"
                        else:
                            order_notice = f"\033[91m✘ {res.get('msg')}\033[0m"

                    # Bersihkan daftar ronde lama
                    if len(self.placed_expiries) > 10:
                        self.placed_expiries.clear()

                    # 3. Render dashboard
                    spinner_char = SPINNER_FRAMES[self.spinner_idx % len(SPINNER_FRAMES)]
                    self.spinner_idx += 1
                    self.render_dashboard(market, signal, spinner_char=spinner_char, order_notice=order_notice)

                except KeyboardInterrupt:
                    raise
                except Exception as loop_err:
                    order_notice = f"\033[93m⚠ Gangguan: {str(loop_err)[:32]}...\033[0m"
                    time.sleep(1)

                time.sleep(config.LOOP_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            self.restore_screen()
            print("\nBot dihentikan oleh pengguna.")
            try:
                bal = self.engine.get_balance()
                print(f"Saldo Akhir: {bal:.2f} USDT")
            except (Exception, KeyboardInterrupt):
                pass

if __name__ == "__main__":
    try:
        bot = BinanceAppPredictionBot()
        bot.run()
    except KeyboardInterrupt:
        print("\nBot dihentikan.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
