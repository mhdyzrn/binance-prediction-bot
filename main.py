import time
import sys
import os
from typing import Optional
import config
from binance_client import BinanceFuturesClient
from strategy import QuantitativeStrategy
from prediction import PredictionEngine
from risk_manager import RiskManager

class BtcPredictionApp:
    """
    Aplikasi Utama Prediksi Kuantitatif 5 Menit BTCUSDT.
    Mendukung mode SIGNAL_ONLY, TESTNET, dan LIVE.
    Menampilkan dashboard terminal terstruktur sesuai spesifikasi.
    """

    def __init__(self):
        self.client = BinanceFuturesClient()
        self.strategy = QuantitativeStrategy()
        self.engine = PredictionEngine(log_filepath="prediction_history.json")
        self.risk_manager = RiskManager(initial_capital=100.0)
        self.last_closed_candle_time: float = 0.0
        self.latest_prediction_record = None
        self.latest_evaluated_record = None
        self.in_cooldown = False
        self.cooldown_until: float = 0.0

    def init_screen(self):
        sys.stdout.write("\033[2J\033[H\033[?25l")
        sys.stdout.flush()

    def restore_screen(self):
        sys.stdout.write("\033[?25h\033[0m\n")
        sys.stdout.flush()

    def render_terminal_dashboard(
        self,
        current_price: float,
        metrics: dict,
        prediction_result: dict,
        last_eval: Optional[any] = None
    ):
        """
        Menampilkan format output terminal sesuai spesifikasi resmi:
        BTCUSDT | 1m
        Harga sekarang: ...
        EMA20: ...
        EMA50: ...
        RSI14: ...
        ATR14: ...
        Volume: VALID / TIDAK
        Liquidity Sweep: BULLISH / BEARISH / NONE
        PREDIKSI 5 MENIT: UP / DOWN / NEUTRAL
        Alasan / Target Evaluasi
        """
        sys.stdout.write("\033[H")

        ema20_str = f"{metrics.get('ema20', 0.0):.2f}" if metrics.get('ema20') else "Menghitung..."
        ema50_str = f"{metrics.get('ema50', 0.0):.2f}" if metrics.get('ema50') else "Menghitung..."
        rsi_val = metrics.get('rsi14')
        rsi_str = f"{rsi_val:.2f}" if rsi_val is not None else "Menghitung..."
        atr_val = metrics.get('atr14')
        atr_str = f"{atr_val:.2f}" if atr_val is not None else "Menghitung..."

        vol_val = metrics.get('signal_vol', 0.0)
        vol_avg = metrics.get('vol_sma20', 0.0)
        if config.ENABLE_VOLUME_FILTER and vol_avg:
            vol_str = "\033[1;92mVALID\033[0m" if vol_val > vol_avg else "\033[1;93mRENDAH\033[0m"
        else:
            vol_str = "NONAKTIF"

        sweep_type = metrics.get('sweep_type', 'NONE')
        if sweep_type == "BULLISH":
            sweep_colored = "\033[1;92mBULLISH\033[0m"
        elif sweep_type == "BEARISH":
            sweep_colored = "\033[1;91mBEARISH\033[0m"
        else:
            sweep_colored = "NONE"

        pred_cat = prediction_result.get("prediction", "NEUTRAL")
        if pred_cat == "UP":
            pred_colored = "\033[1;42;30m PREDIKSI 5 MENIT: UP \033[0m"
        elif pred_cat == "DOWN":
            pred_colored = "\033[1;41;37m PREDIKSI 5 MENIT: DOWN \033[0m"
        else:
            pred_colored = "\033[1;43;30m PREDIKSI 5 MENIT: NEUTRAL \033[0m"

        mode_badge = f"\033[1;96m[MODE: {config.TRADING_MODE}]\033[0m"
        stats = self.engine.get_performance_summary()

        output_lines = [
            f"====================================================\033[K",
            f"  {config.SYMBOL} | {config.ANALYSIS_TIMEFRAME}            {mode_badge}\033[K",
            f"====================================================\033[K",
            f"Harga sekarang  : \033[1m{current_price:,.2f} USDT\033[0m\033[K",
            f"EMA20           : {ema20_str}\033[K",
            f"EMA50           : {ema50_str}\033[K",
            f"RSI14           : {rsi_str}\033[K",
            f"ATR14           : {atr_str}\033[K",
            f"Volume          : {vol_str}\033[K",
            f"Liquidity Sweep : {sweep_colored}\033[K",
            f"----------------------------------------------------\033[K",
            f"{pred_colored}\033[K",
        ]

        if pred_cat == "NEUTRAL":
            output_lines.append(f"Alasan          : {prediction_result.get('reason', 'Tidak ada sinyal.')}\033[K")
        else:
            output_lines.append(f"Konfirmasi      : {prediction_result.get('reason', '')}\033[K")
            output_lines.append(f"Skor Confluence : {prediction_result.get('score', 0):.0f} / 100\033[K")

        # Blok Evaluasi Target 5 Menit
        output_lines.append(f"----------------------------------------------------\033[K")
        if last_eval and last_eval.evaluated:
            hasil_str = "\033[1;92mBENAR\033[0m" if last_eval.is_direction_correct else "\033[1;91mSALAH\033[0m"
            econ_str = "\033[1;92mPROFIT\033[0m" if last_eval.is_profitable else "\033[1;91mLOSS\033[0m"
            pnl_sign = "+" if (last_eval.net_pnl_pct or 0) >= 0 else ""
            output_lines.extend([
                f"\033[1mTarget Evaluasi Terakhir ({last_eval.prediction_id}):\033[0m\033[K",
                f"Harga entry ({last_eval.category}) : {last_eval.entry_price:,.2f} USDT\033[K",
                f"Harga 5m kemudian   : {last_eval.actual_price_5m:,.2f} USDT\033[K",
                f"Akurasi Arah        : {hasil_str}\033[K",
                f"Net Return (fee+slip): {pnl_sign}{last_eval.net_pnl_pct:.4f}% ({econ_str})\033[K"
            ])
        else:
            output_lines.append(f"Target evaluasi : Menunggu candle 5m berikutnya...\033[K")

        output_lines.extend([
            f"====================================================\033[K",
            f"STATISTIK EVALUASI TERKALIBRASI:\033[K",
            f"Total Evaluasi   : {stats['total_evaluated']} trade (UP: {stats['count_up']} | DOWN: {stats['count_down']})\033[K",
            f"Directional Acc  : \033[1;36m{stats['directional_accuracy']}%\033[0m (UP: {stats['up_accuracy']}% | DOWN: {stats['down_accuracy']}%)\033[K",
            f"Economic Win Rate: \033[1;32m{stats['economic_win_rate']}%\033[0m (Setelah Taker Fee & Slippage)\033[K",
            f"Net PnL Kumulatif: {stats['cum_net_pnl_pct']:+.4f}%\033[K",
            f"====================================================\033[K",
            f"Tekan Ctrl+C untuk berhenti secara aman.\033[K"
        ])

        sys.stdout.write("\n".join(output_lines) + "\n")
        sys.stdout.flush()

    def run(self):
        print(f"Menghubungkan ke Binance Futures ({config.SYMBOL})...")
        ok, msg, initial_price = self.client.test_connection()
        if not ok:
            print(f"Gagal koneksi: {msg}")
            sys.exit(1)

        print(f"Terhubung! Harga awal: ${initial_price:,.2f} USDT")
        print(f"Memuat riwayat candle awal...")
        time.sleep(1.0)
        self.init_screen()

        current_pred_res = {"prediction": "NEUTRAL", "reason": "Menunggu konfirmasi candle 1m tertutup pertama."}
        current_metrics = {}

        try:
            while True:
                now = time.time()
                # Cek Cooldown posisi 5m
                self.in_cooldown = (now < self.cooldown_until)

                # Ambil candle tertutup
                closed_candles = self.client.get_closed_klines(limit=65)
                _, _, spread = self.client.get_order_book_spread()

                if closed_candles:
                    latest_closed = closed_candles[-1]
                    closed_time = latest_closed["close_time"]
                    curr_price = latest_closed["close"]

                    # 1. Evaluasi prediksi lama yang sudah mencapai horizon 5 menit
                    evaluated_list = self.engine.evaluate_pending(closed_time, curr_price)
                    if evaluated_list:
                        self.latest_evaluated_record = evaluated_list[-1]

                    # 2. Jika ada candle baru yang baru saja ditutup
                    if closed_time > self.last_closed_candle_time:
                        self.last_closed_candle_time = closed_time

                        # Evaluasi strategi pada candle tertutup
                        eval_res = self.strategy.evaluate_market(
                            closed_candles,
                            current_spread=spread,
                            in_cooldown=self.in_cooldown
                        )
                        current_pred_res = eval_res
                        current_metrics = eval_res.get("metrics", {})

                        pred_dir = eval_res.get("prediction", "NEUTRAL")
                        if pred_dir in ["UP", "DOWN"]:
                            # Catat prediksi baru
                            rec = self.engine.record_prediction(
                                symbol=config.SYMBOL,
                                category=pred_dir,
                                entry_price=curr_price,
                                score=eval_res.get("score", 0.0),
                                reason=eval_res.get("reason", ""),
                                metrics=current_metrics,
                                candle_timestamp=closed_time
                            )
                            self.latest_prediction_record = rec
                            self.cooldown_until = now + (config.COOLDOWN_MINUTES * 60)

                            # Validasi & Eksekusi Order jika mode TESTNET atau LIVE
                            risk_check = self.risk_manager.validate_trade_allowed(
                                pred_dir,
                                current_spread=spread,
                                current_atr=current_metrics.get("atr14", 20.0)
                            )
                            if risk_check["allowed"] and config.TRADING_MODE in ["TESTNET", "LIVE"]:
                                # Eksekusi order testnet/live
                                pass

                    self.render_terminal_dashboard(
                        current_price=curr_price,
                        metrics=current_metrics,
                        prediction_result=current_pred_res,
                        last_eval=self.latest_evaluated_record
                    )

                time.sleep(1.0)

        except KeyboardInterrupt:
            self.restore_screen()
            print("\nBot dihentikan oleh pengguna.")
            stats = self.engine.get_performance_summary()
            print("\n" + "=" * 50)
            print("         RINGKASAN SESI BOT         ")
            print("=" * 50)
            print(f"Total Prediksi Dicatat : {stats['total_predictions']}")
            print(f"Total Selesai Dievaluasi: {stats['total_evaluated']}")
            print(f"Directional Accuracy   : {stats['directional_accuracy']}%")
            print(f"Economic Win Rate      : {stats['economic_win_rate']}%")
            print(f"Net PnL Kumulatif      : {stats['cum_net_pnl_pct']:+.4f}%")
            print("=" * 50 + "\n")

if __name__ == "__main__":
    app = BtcPredictionApp()
    app.run()
