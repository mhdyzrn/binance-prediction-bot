import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from liquidity_sweep import LiquiditySweepDetector
from strategy import QuantitativeStrategy
import config

class TestStrategyAndSweep(unittest.TestCase):

    def setUp(self):
        self.detector = LiquiditySweepDetector(lookback_period=20)
        self.strategy = QuantitativeStrategy(self.detector)

    def test_bullish_liquidity_sweep_detection(self):
        # 20 candle sebelumnya berkisar antara 100 s.d 120 (Swing Low = 100.0, Swing High = 120.0)
        prior_candles = []
        for i in range(20):
            prior_candles.append({
                "open": 105.0,
                "high": 120.0 if i == 5 else 115.0,
                "low": 100.0 if i == 10 else 102.0,
                "close": 110.0,
                "volume": 50.0,
                "is_closed": True
            })

        # Candle sinyal: Menembus swing low 100.0 (low = 95.0), kembali ditutup di 103.0 (di atas 100), candle hijau
        signal_candle = {
            "open": 98.0,
            "high": 108.0,
            "low": 95.0,
            "close": 104.0,
            "volume": 120.0,
            "is_closed": True
        }

        all_candles = prior_candles + [signal_candle]
        sweep_res = self.detector.detect_sweep(all_candles)

        self.assertTrue(sweep_res["detected"])
        self.assertEqual(sweep_res["type"], "BULLISH")
        self.assertEqual(sweep_res["swing_low"], 100.0)
        self.assertEqual(sweep_res["penetration"], 5.0)

    def test_bearish_liquidity_sweep_detection(self):
        # 20 candle sebelumnya: Swing High = 150.0, Swing Low = 130.0
        prior_candles = []
        for i in range(20):
            prior_candles.append({
                "open": 135.0,
                "high": 150.0 if i == 7 else 145.0,
                "low": 130.0 if i == 3 else 132.0,
                "close": 140.0,
                "volume": 60.0,
                "is_closed": True
            })

        # Candle sinyal: Menembus swing high 150.0 (high = 155.0), ditutup di 148.0 (di bawah 150), candle merah
        signal_candle = {
            "open": 152.0,
            "high": 155.0,
            "low": 146.0,
            "close": 148.0,
            "volume": 150.0,
            "is_closed": True
        }

        all_candles = prior_candles + [signal_candle]
        sweep_res = self.detector.detect_sweep(all_candles)

        self.assertTrue(sweep_res["detected"])
        self.assertEqual(sweep_res["type"], "BEARISH")
        self.assertEqual(sweep_res["swing_high"], 150.0)
        self.assertEqual(sweep_res["penetration"], 5.0)

    def test_spread_filter(self):
        candles = [{"open": 100, "high": 110, "low": 90, "close": 105, "volume": 100, "is_closed": True}] * 60
        res = self.strategy.evaluate_market(candles, current_spread=10.0, in_cooldown=False)
        self.assertEqual(res["prediction"], "NEUTRAL")
        self.assertIn("Spread", res["reason"])

    def test_cooldown_filter(self):
        candles = [{"open": 100, "high": 110, "low": 90, "close": 105, "volume": 100, "is_closed": True}] * 60
        res = self.strategy.evaluate_market(candles, current_spread=0.5, in_cooldown=True)
        self.assertEqual(res["prediction"], "NEUTRAL")
        self.assertIn("Cooldown", res["reason"])

if __name__ == "__main__":
    unittest.main()
