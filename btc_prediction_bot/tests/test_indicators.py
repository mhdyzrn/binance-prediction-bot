import unittest
import sys
import os

# Menambahkan direktori root proyek ke sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from indicators import IndicatorCalculator

class TestIndicatorCalculator(unittest.TestCase):

    def test_ema_calculation(self):
        # 20 closes konstan 100
        closes = [100.0] * 25
        ema20 = IndicatorCalculator.calculate_ema(closes, 20)
        self.assertIsNotNone(ema20)
        self.assertAlmostEqual(ema20, 100.0, places=2)

        # Uji data tidak cukup
        self.assertIsNone(IndicatorCalculator.calculate_ema([100.0] * 10, 20))

    def test_ema_uptrend(self):
        # Uptrend bertahap
        closes = [float(i) for i in range(1, 35)]
        ema20 = IndicatorCalculator.calculate_ema(closes, 20)
        self.assertIsNotNone(ema20)
        # Pada uptrend kontinu, Close terakhir selalu di atas EMA
        self.assertGreater(closes[-1], ema20)

    def test_rsi_calculation(self):
        # Uptrend kuat: semua candle naik
        closes_up = [100.0 + (i * 2.0) for i in range(25)]
        rsi_up = IndicatorCalculator.calculate_rsi(closes_up, 14)
        self.assertIsNotNone(rsi_up)
        self.assertGreater(rsi_up, 80.0)

        # Downtrend kuat: semua candle turun
        closes_down = [200.0 - (i * 2.0) for i in range(25)]
        rsi_down = IndicatorCalculator.calculate_rsi(closes_down, 14)
        self.assertIsNotNone(rsi_down)
        self.assertLess(rsi_down, 20.0)

        # Data kurang dari period + 1
        self.assertIsNone(IndicatorCalculator.calculate_rsi([100.0] * 10, 14))

    def test_atr_calculation(self):
        highs = [105.0] * 20
        lows = [95.0] * 20
        closes = [100.0] * 20
        atr = IndicatorCalculator.calculate_atr(highs, lows, closes, 14)
        self.assertIsNotNone(atr)
        self.assertAlmostEqual(atr, 10.0, places=2)

        # Insufficient data
        self.assertIsNone(IndicatorCalculator.calculate_atr(highs[:5], lows[:5], closes[:5], 14))

    def test_candle_metrics(self):
        candle = {
            "open": 100.0,
            "high": 115.0,
            "low": 95.0,
            "close": 110.0
        }
        metrics = IndicatorCalculator.calculate_candle_metrics(candle)
        self.assertEqual(metrics["body"], 10.0)
        self.assertEqual(metrics["range"], 20.0)
        self.assertEqual(metrics["upper_shadow"], 5.0)
        self.assertEqual(metrics["lower_shadow"], 5.0)
        self.assertEqual(metrics["is_bullish"], 1.0)

if __name__ == "__main__":
    unittest.main()
