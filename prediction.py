import time
import json
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import config

@dataclass
class PredictionRecord:
    prediction_id: str
    symbol: str
    prediction_time: float
    prediction_time_str: str
    target_eval_time: float
    target_eval_time_str: str
    category: str                   # 'UP', 'DOWN', 'NEUTRAL'
    entry_price: float
    score: float
    reason: str
    metrics: Dict[str, Any]
    actual_price_5m: Optional[float] = None
    evaluated: bool = False
    is_direction_correct: Optional[bool] = None
    price_change: Optional[float] = None
    price_change_pct: Optional[float] = None
    gross_pnl_pct: Optional[float] = None
    net_pnl_pct: Optional[float] = None
    is_profitable: Optional[bool] = None

class PredictionEngine:
    """
    Sistem Evaluasi & Pelacakan Prediksi Terpisah (Separated Prediction Evaluator).
    Memisahkan antara 'Akurasi Arah (Directional Accuracy)' dan 'Profitabilitas Realistis (Net PnL)',
    karena prediksi arah yang benar belum tentu menutup biaya taker fee Binance Futures dan slippage.
    """

    def __init__(self, log_filepath: str = "prediction_history.json"):
        self.log_filepath = log_filepath
        self.records: List[PredictionRecord] = []
        self.load_history()

    def record_prediction(
        self,
        symbol: str,
        category: str,
        entry_price: float,
        score: float,
        reason: str,
        metrics: Dict[str, Any],
        candle_timestamp: Optional[float] = None
    ) -> PredictionRecord:
        """
        Mencatat prediksi baru pada candle tertutup T, menetapkan target evaluasi tepat di T + 5 menit.
        """
        now = candle_timestamp or time.time()
        now_dt_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        target_time = now + (config.PREDICTION_HORIZON_MINUTES * 60)
        target_dt_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(target_time))
        pred_id = f"PRED-{int(now)}-{category}"

        rec = PredictionRecord(
            prediction_id=pred_id,
            symbol=symbol,
            prediction_time=now,
            prediction_time_str=now_dt_str,
            target_eval_time=target_time,
            target_eval_time_str=target_dt_str,
            category=category,
            entry_price=round(entry_price, 2),
            score=round(score, 1),
            reason=reason,
            metrics=metrics
        )
        self.records.append(rec)
        self.save_history()
        return rec

    def evaluate_pending(self, current_candle_time: float, current_close_price: float) -> List[PredictionRecord]:
        """
        Mengevaluasi prediksi yang telah mencapai batas horizon 5 menit.
        Menghitung directional accuracy dan net profitability setelah biaya trading.
        """
        evaluated_now: List[PredictionRecord] = []
        roundtrip_cost_pct = (config.TAKER_FEE_RATE * 2.0 + config.SLIPPAGE_RATE * 2.0) * 100.0

        for rec in self.records:
            if rec.evaluated:
                continue

            # Jika waktu candle saat ini sudah mencapai atau melewati target evaluasi T + 5m
            if current_candle_time >= rec.target_eval_time:
                rec.evaluated = True
                rec.actual_price_5m = round(current_close_price, 2)
                p_change = rec.actual_price_5m - rec.entry_price
                p_change_pct = (p_change / rec.entry_price) * 100.0 if rec.entry_price > 0 else 0.0

                rec.price_change = round(p_change, 2)
                rec.price_change_pct = round(p_change_pct, 4)

                if rec.category == "UP":
                    rec.is_direction_correct = (p_change > 0.0)
                    rec.gross_pnl_pct = round(p_change_pct, 4)
                    rec.net_pnl_pct = round(p_change_pct - roundtrip_cost_pct, 4)
                    rec.is_profitable = (rec.net_pnl_pct > 0.0)
                elif rec.category == "DOWN":
                    rec.is_direction_correct = (p_change < 0.0)
                    rec.gross_pnl_pct = round(-p_change_pct, 4)
                    rec.net_pnl_pct = round(-p_change_pct - roundtrip_cost_pct, 4)
                    rec.is_profitable = (rec.net_pnl_pct > 0.0)
                else: # NEUTRAL
                    rec.is_direction_correct = None
                    rec.gross_pnl_pct = 0.0
                    rec.net_pnl_pct = 0.0
                    rec.is_profitable = None

                evaluated_now.append(rec)

        if evaluated_now:
            self.save_history()

        return evaluated_now

    def get_performance_summary(self) -> Dict[str, Any]:
        """Menghitung metrik performa statistik terkalibrasi"""
        eval_records = [r for r in self.records if r.evaluated and r.category in ["UP", "DOWN"]]
        total_eval = len(eval_records)

        up_records = [r for r in eval_records if r.category == "UP"]
        down_records = [r for r in eval_records if r.category == "DOWN"]
        neutral_records = [r for r in self.records if r.category == "NEUTRAL"]

        up_correct = sum(1 for r in up_records if r.is_direction_correct)
        down_correct = sum(1 for r in down_records if r.is_direction_correct)
        total_correct = up_correct + down_correct

        up_acc = (up_correct / len(up_records) * 100.0) if up_records else 0.0
        down_acc = (down_correct / len(down_records) * 100.0) if down_records else 0.0
        overall_acc = (total_correct / total_eval * 100.0) if total_eval > 0 else 0.0

        profitable_trades = sum(1 for r in eval_records if r.is_profitable)
        econ_win_rate = (profitable_trades / total_eval * 100.0) if total_eval > 0 else 0.0
        net_pnls = [r.net_pnl_pct for r in eval_records if r.net_pnl_pct is not None]
        avg_net_pnl = (sum(net_pnls) / len(net_pnls)) if net_pnls else 0.0
        cum_net_pnl = sum(net_pnls) if net_pnls else 0.0

        return {
            "total_predictions": len(self.records),
            "total_evaluated": total_eval,
            "count_up": len(up_records),
            "count_down": len(down_records),
            "count_neutral": len(neutral_records),
            "up_accuracy": round(up_acc, 2),
            "down_accuracy": round(down_acc, 2),
            "directional_accuracy": round(overall_acc, 2),
            "profitable_count": profitable_trades,
            "economic_win_rate": round(econ_win_rate, 2),
            "avg_net_pnl_pct": round(avg_net_pnl, 4),
            "cum_net_pnl_pct": round(cum_net_pnl, 4)
        }

    def save_history(self):
        try:
            with open(self.log_filepath, "w", encoding="utf-8") as f:
                json.dump([asdict(r) for r in self.records[-200:]], f, indent=2)
        except Exception:
            pass

    def load_history(self):
        if os.path.exists(self.log_filepath):
            try:
                with open(self.log_filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.records = [PredictionRecord(**d) for d in data]
            except Exception:
                pass
