import sys
import os
import time
import argparse
from typing import List, Dict, Any, Tuple
import config
from binance_client import BinanceFuturesClient
from strategy import QuantitativeStrategy
from liquidity_sweep import LiquiditySweepDetector

class QuantitativeBacktester:
    """
    Modul Backtesting & Evaluasi Kuantitatif untuk Prediksi 5 Menit BTCUSDT.
    - Zero Look-Ahead Bias: Sinyal dihasilkan hanya saat candle t ditutup.
    - Horizon 5 Menit: Evaluasi harga pada candle t + 5.
    - Split Berdasarkan Waktu: Memisahkan In-Sample (Train/Val) dan Out-of-Sample (Test).
    - Memisahkan Directional Accuracy (Akurasi Arah) dari Real Profitability (setelah fee + slippage).
    """

    def __init__(self, client: Optional[BinanceFuturesClient] = None):
        self.client = client or BinanceFuturesClient()
        self.strategy = QuantitativeStrategy(LiquiditySweepDetector(lookback_period=config.SWING_LOOKBACK))
        self.roundtrip_friction = (config.TAKER_FEE_RATE * 2.0 + config.SLIPPAGE_RATE * 2.0)

    def fetch_historical_candles(self, total_candles: int = 1500) -> List[Dict[str, Any]]:
        """Mengambil data historis candle 1 menit Binance Futures secara berurutan"""
        print(f"Mengambil {total_candles} candle 1m historis dari Binance Futures...")
        candles: List[Dict[str, Any]] = []
        end_time_ms = None
        remaining = total_candles

        while remaining > 0:
            batch_size = min(remaining, 1000)
            url = f"{self.client.base_url}/fapi/v1/klines"
            params = {
                "symbol": config.SYMBOL,
                "interval": "1m",
                "limit": batch_size
            }
            if end_time_ms:
                params["endTime"] = end_time_ms

            try:
                resp = self.client.session.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    raw = resp.json()
                    if not raw:
                        break
                    batch_candles = []
                    for k in raw:
                        batch_candles.append({
                            "open_time": int(k[0]) / 1000.0,
                            "open": float(k[1]),
                            "high": float(k[2]),
                            "low": float(k[3]),
                            "close": float(k[4]),
                            "volume": float(k[5]),
                            "close_time": int(k[6]) / 1000.0,
                            "is_closed": True
                        })
                    candles = batch_candles + candles
                    remaining -= len(batch_candles)
                    end_time_ms = int(raw[0][0]) - 1
                    time.sleep(0.2)
                else:
                    break
            except Exception as e:
                print(f"Error fetching historical data: {e}")
                break

        print(f"Berhasil mengunduh {len(candles)} candle historis.")
        return candles

    def run_simulation(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Menjalankan simulasi prediksi 5 menit candle demi candle"""
        horizon = config.PREDICTION_HORIZON_MINUTES
        min_start = max(config.EMA_SLOW_PERIOD + 10, config.SWING_LOOKBACK + 10)
        n = len(candles)

        if n < min_start + horizon + 5:
            return {"error": "Jumlah candle tidak mencukupi untuk simulasi"}

        trades = []
        neutral_count = 0
        up_count = 0
        down_count = 0

        # Cooldown tracker
        last_entry_index = -999

        for i in range(min_start, n - horizon):
            # Cek cooldown posisi 5m
            in_cooldown = (i - last_entry_index < horizon)

            # Irisan data strictly up to candle i (zero look-ahead bias)
            visible_candles = candles[:i + 1]

            # Evaluasi strategi
            res = self.strategy.evaluate_market(visible_candles, current_spread=0.5, in_cooldown=in_cooldown)
            pred = res["prediction"]

            if pred == "NEUTRAL":
                neutral_count += 1
                continue

            last_entry_index = i
            entry_price = candles[i]["close"]
            exit_price = candles[i + horizon]["close"]
            entry_time = candles[i]["close_time"]
            exit_time = candles[i + horizon]["close_time"]

            # Price delta 5m kemudian
            price_change = exit_price - entry_price
            price_change_pct = (price_change / entry_price)

            if pred == "UP":
                up_count += 1
                is_correct = (price_change > 0.0)
                gross_ret = price_change_pct
                net_ret = price_change_pct - self.roundtrip_friction
            else: # DOWN
                down_count += 1
                is_correct = (price_change < 0.0)
                gross_ret = -price_change_pct
                net_ret = -price_change_pct - self.roundtrip_friction

            trades.append({
                "index": i,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "prediction": pred,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "price_change": price_change,
                "price_change_pct": price_change_pct * 100.0,
                "is_correct": is_correct,
                "gross_return_pct": gross_ret * 100.0,
                "net_return_pct": net_ret * 100.0,
                "is_profitable": (net_ret > 0.0),
                "score": res.get("score", 0.0)
            })

        # -------------------------------------------------------------
        # PERHITUNGAN STATISTIK & METRIK
        # -------------------------------------------------------------
        total_signals = len(trades)
        if total_signals == 0:
            return {
                "total_candles": n,
                "total_signals": 0,
                "up_count": 0,
                "down_count": 0,
                "neutral_count": neutral_count,
                "accuracy": 0.0,
                "trades": []
            }

        up_trades = [t for t in trades if t["prediction"] == "UP"]
        down_trades = [t for t in trades if t["prediction"] == "DOWN"]

        up_correct = sum(1 for t in up_trades if t["is_correct"])
        down_correct = sum(1 for t in down_trades if t["is_correct"])
        total_correct = up_correct + down_correct

        up_acc = (up_correct / len(up_trades) * 100.0) if up_trades else 0.0
        down_acc = (down_correct / len(down_trades) * 100.0) if down_trades else 0.0
        overall_acc = (total_correct / total_signals * 100.0)

        # Confusion Matrix
        # TP_UP: Pred UP dan Aktual Naik
        # FP_UP: Pred UP dan Aktual Turun
        # TP_DOWN: Pred DOWN dan Aktual Turun
        # FP_DOWN: Pred DOWN dan Aktual Naik
        tp_up = up_correct
        fp_up = len(up_trades) - up_correct
        tp_down = down_correct
        fp_down = len(down_trades) - down_correct

        prec_up = (tp_up / (tp_up + fp_up) * 100.0) if (tp_up + fp_up) > 0 else 0.0
        prec_down = (tp_down / (tp_down + fp_down) * 100.0) if (tp_down + fp_down) > 0 else 0.0

        # Profitabilitas & Drawdown
        profitable_trades = sum(1 for t in trades if t["is_profitable"])
        econ_win_rate = (profitable_trades / total_signals * 100.0)

        cum_equity = 100.0
        equity_curve = [100.0]
        peak = 100.0
        max_dd = 0.0

        for t in trades:
            cum_equity *= (1.0 + (t["net_return_pct"] / 100.0))
            equity_curve.append(cum_equity)
            if cum_equity > peak:
                peak = cum_equity
            dd = (peak - cum_equity) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        avg_price_change_usdt = sum(t["price_change"] for t in trades) / total_signals
        avg_net_ret = sum(t["net_return_pct"] for t in trades) / total_signals

        return {
            "total_candles": n,
            "total_signals": total_signals,
            "up_count": len(up_trades),
            "down_count": len(down_trades),
            "neutral_count": neutral_count,
            "overall_accuracy": round(overall_acc, 2),
            "up_accuracy": round(up_acc, 2),
            "down_accuracy": round(down_acc, 2),
            "precision_up": round(prec_up, 2),
            "precision_down": round(prec_down, 2),
            "confusion_matrix": {
                "tp_up": tp_up,
                "fp_up": fp_up,
                "tp_down": tp_down,
                "fp_down": fp_down
            },
            "avg_price_change_usdt": round(avg_price_change_usdt, 2),
            "avg_net_return_pct": round(avg_net_ret, 4),
            "cumulative_return_pct": round(cum_equity - 100.0, 2),
            "economic_win_rate": round(econ_win_rate, 2),
            "max_drawdown_pct": round(max_dd * 100.0, 2),
            "friction_per_trade_pct": round(self.roundtrip_friction * 100.0, 2),
            "trades": trades
        }

    def print_report(self, label: str, results: Dict[str, Any]) -> None:
        """Menampilkan laporan statistik backtesting format terminal yang rapi"""
        print("\n" + "=" * 65)
        print(f"        LAPORAN BACKTEST: {label.upper()} ({config.SYMBOL})")
        print("=" * 65)
        if "error" in results or results.get("total_signals", 0) == 0:
            print(f"Info: {results.get('error', 'Tidak ada sinyal yang dihasilkan.')}")
            print("=" * 65)
            return

        print(f"Data Sampel Candle  : {results['total_candles']} candle 1m")
        print(f"Total Sinyal Aktif  : {results['total_signals']} trade (UP: {results['up_count']}, DOWN: {results['down_count']})")
        print(f"Sinyal Netral/Filter: {results['neutral_count']} candle dilewati")
        print("-" * 65)
        print("1. EVALUASI AKURASI ARAH (DIRECTIONAL ACCURACY):")
        print(f"  • Akurasi Keseluruhan : \033[1;36m{results['overall_accuracy']}%\033[0m")
        print(f"  • Akurasi Sinyal UP   : {results['up_accuracy']}% (Precision: {results['precision_up']}%)")
        print(f"  • Akurasi Sinyal DOWN : {results['down_accuracy']}% (Precision: {results['precision_down']}%)")
        print(f"  • Confusion Matrix    : TP_UP={results['confusion_matrix']['tp_up']} | FP_UP={results['confusion_matrix']['fp_up']}")
        print(f"                          TP_DOWN={results['confusion_matrix']['tp_down']} | FP_DOWN={results['confusion_matrix']['fp_down']}")
        print("-" * 65)
        print("2. EVALUASI EKONOMI & TRADING (SETELAH BIAYA TAKER & SLIPPAGE):")
        print(f"  • Biaya Gesekan Pasar : -{results['friction_per_trade_pct']}% per trade (Taker 0.05%x2 + Slip 0.02%x2)")
        print(f"  • Economic Win Rate   : \033[1;32m{results['economic_win_rate']}%\033[0m (Trade yang untung bersih)")
        print(f"  • Rata-rata Net PnL   : {results['avg_net_return_pct']:+.4f}% per sinyal")
        print(f"  • Rata-rata Δ Harga   : ${results['avg_price_change_usdt']:+.2f} per 5 menit")
        print(f"  • Cumulative Return   : \033[1;33m{results['cumulative_return_pct']:+.2f}%\033[0m")
        print(f"  • Maximum Drawdown    : \033[1;31m{results['max_drawdown_pct']}%\033[0m")
        print("=" * 65 + "\n")

def run_backtest_cli():
    parser = argparse.ArgumentParser(description="Backtester Prediksi 5 Menit BTCUSDT")
    parser.add_argument("--candles", type=int, default=1200, help="Jumlah total candle 1m yang diuji (default: 1200)")
    parser.add_argument("--split", type=float, default=0.6, help="Rasio In-Sample vs Out-of-Sample (default: 0.6)")
    args = parser.parse_args()

    backtester = QuantitativeBacktester()
    candles = backtester.fetch_historical_candles(total_candles=args.candles)

    if len(candles) < 150:
        print("Data candle tidak mencukupi.")
        return

    split_idx = int(len(candles) * args.split)
    train_candles = candles[:split_idx]
    test_candles = candles[split_idx:]

    print(f"\nMemisahkan Dataset:")
    print(f"  • In-Sample / Tuning   : {len(train_candles)} candle ({time.strftime('%Y-%m-%d %H:%M', time.localtime(train_candles[0]['open_time']))} s.d {time.strftime('%Y-%m-%d %H:%M', time.localtime(train_candles[-1]['open_time']))})")
    print(f"  • Out-of-Sample / Test : {len(test_candles)} candle ({time.strftime('%Y-%m-%d %H:%M', time.localtime(test_candles[0]['open_time']))} s.d {time.strftime('%Y-%m-%d %H:%M', time.localtime(test_candles[-1]['open_time']))})")

    # Uji 1: In-Sample
    res_train = backtester.run_simulation(train_candles)
    backtester.print_report("In-Sample (Training / Validation)", res_train)

    # Uji 2: Out-of-Sample (Evaluasi Terisolasi)
    res_test = backtester.run_simulation(test_candles)
    backtester.print_report("Out-of-Sample (Final Unseen Test)", res_test)

if __name__ == "__main__":
    run_backtest_cli()
