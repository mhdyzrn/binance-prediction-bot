import unittest
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prediction import PredictionEngine

class TestPredictionEngine(unittest.TestCase):

    def setUp(self):
        # Gunakan file log temporer
        self.log_file = "test_prediction_log.json"
        if os.path.exists(self.log_file):
            os.remove(self.log_file)
        self.engine = PredictionEngine(log_filepath=self.log_file)

    def tearDown(self):
        if os.path.exists(self.log_file):
            try:
                os.remove(self.log_file)
            except Exception:
                pass

    def test_record_and_evaluate_up(self):
        t0 = 1000000.0
        rec = self.engine.record_prediction(
            symbol="BTCUSDT",
            category="UP",
            entry_price=80000.0,
            score=85.0,
            reason="Bullish sweep test",
            metrics={},
            candle_timestamp=t0
        )
        self.assertEqual(rec.category, "UP")
        self.assertEqual(rec.target_eval_time, t0 + 300)
        self.assertFalse(rec.evaluated)

        # Evaluasi sebelum waktunya (t0 + 120s) -> belum dievaluasi
        pending = self.engine.evaluate_pending(t0 + 120, 80500.0)
        self.assertEqual(len(pending), 0)
        self.assertFalse(rec.evaluated)

        # Evaluasi tepat waktu (t0 + 300s) dengan harga naik ke 80200.0
        evaluated = self.engine.evaluate_pending(t0 + 300, 80200.0)
        self.assertEqual(len(evaluated), 1)
        self.assertTrue(rec.evaluated)
        self.assertTrue(rec.is_direction_correct)
        self.assertGreater(rec.price_change, 0.0)
        # Gross profit +0.25%, net profit setelah fee 0.14% harus positif
        self.assertTrue(rec.is_profitable)

    def test_directional_correct_but_unprofitable(self):
        """
        Menguji kasus krusial: Prediksi arah benar (harga naik sangat tipis +$10 / +0.012%),
        namun rugi setelah dipotong fee taker Binance & slippage (net return negatif).
        """
        t0 = 2000000.0
        rec = self.engine.record_prediction(
            symbol="BTCUSDT",
            category="UP",
            entry_price=80000.0,
            score=80.0,
            reason="Micro up test",
            metrics={},
            candle_timestamp=t0
        )
        # Naik hanya $10 (0.0125%), fee taker 0.14%
        evaluated = self.engine.evaluate_pending(t0 + 300, 80010.0)
        self.assertEqual(len(evaluated), 1)
        self.assertTrue(rec.is_direction_correct)   # Arah BENAR
        self.assertFalse(rec.is_profitable)         # Tapi TIDAK PROFIT (Rugi fee)
        self.assertLess(rec.net_pnl_pct, 0.0)

    def test_summary_metrics(self):
        t0 = 3000000.0
        # 1 Trade UP Win
        self.engine.record_prediction("BTCUSDT", "UP", 80000.0, 85.0, "Test UP Win", {}, candle_timestamp=t0)
        self.engine.evaluate_pending(t0 + 300, 80300.0)

        # 1 Trade DOWN Win
        self.engine.record_prediction("BTCUSDT", "DOWN", 80000.0, 85.0, "Test DOWN Win", {}, candle_timestamp=t0 + 600)
        self.engine.evaluate_pending(t0 + 900, 79700.0)

        summary = self.engine.get_performance_summary()
        self.assertEqual(summary["total_evaluated"], 2)
        self.assertEqual(summary["directional_accuracy"], 100.0)
        self.assertEqual(summary["economic_win_rate"], 100.0)

if __name__ == "__main__":
    unittest.main()
