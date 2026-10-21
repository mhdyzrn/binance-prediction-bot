from typing import List, Dict, Any, Optional

class LiquiditySweepDetector:
    """
    Detektor Liquidity Sweep Kuantitatif.
    Mendeteksi jebakan likuiditas (fakeout / stop hunt) pada level swing high dan swing low.
    Bebas dari look-ahead bias: swing level dihitung murni dari N candle sebelum candle sinyal.
    """

    def __init__(self, lookback_period: int = 20):
        self.lookback_period = lookback_period

    def detect_sweep(self, closed_candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Menganalisis candle tertutup terbaru (signal candle) terhadap N candle sebelumnya.
        
        Args:
            closed_candles: List candle 1m yang sudah selesai/tertutup (minimal lookback + 1 candle).
            
        Returns:
            Dict hasil deteksi: type ('BULLISH', 'BEARISH', 'NONE'), swing_high, swing_low, detail.
        """
        min_required = self.lookback_period + 1
        if not closed_candles or len(closed_candles) < min_required:
            return {
                "detected": False,
                "type": "NONE",
                "swing_high": None,
                "swing_low": None,
                "penetration": 0.0,
                "rejection_wick": 0.0,
                "reason": f"Data candle belum cukup (butuh {min_required}, ada {len(closed_candles)})"
            }

        # Candle sinyal yang baru saja ditutup (candle terakhir)
        signal_candle = closed_candles[-1]
        
        # 20 candle sebelumnya (strictly excluding signal candle untuk mencegah look-ahead bias)
        prior_candles = closed_candles[-(self.lookback_period + 1): -1]

        highs = [float(c["high"]) for c in prior_candles]
        lows = [float(c["low"]) for c in prior_candles]

        swing_high = max(highs)
        swing_low = min(lows)

        curr_open = float(signal_candle["open"])
        curr_high = float(signal_candle["high"])
        curr_low = float(signal_candle["low"])
        curr_close = float(signal_candle["close"])

        # -------------------------------------------------------------
        # 1. BULLISH LIQUIDITY SWEEP
        # -------------------------------------------------------------
        # Syarat 1: Low menembus di bawah Swing Low sebelumnya
        # Syarat 2: Close kembali ditutup di atas Swing Low tersebut
        # Syarat 3: Konfirmasi candle bullish (Close > Open)
        if (curr_low < swing_low) and (curr_close > swing_low) and (curr_close > curr_open):
            penetration = round(swing_low - curr_low, 2)
            lower_wick = round(min(curr_open, curr_close) - curr_low, 2)
            return {
                "detected": True,
                "type": "BULLISH",
                "swing_high": swing_high,
                "swing_low": swing_low,
                "penetration": penetration,
                "rejection_wick": lower_wick,
                "reason": (
                    f"Bullish Sweep Terkonfirmasi! Low (${curr_low:,.2f}) menyapu Swing Low (${swing_low:,.2f}), "
                    f"rejection ditutup di atas swing (${curr_close:,.2f}) dengan candle hijau"
                )
            }

        # -------------------------------------------------------------
        # 2. BEARISH LIQUIDITY SWEEP
        # -------------------------------------------------------------
        # Syarat 1: High menembus di atas Swing High sebelumnya
        # Syarat 2: Close kembali ditutup di bawah Swing High tersebut
        # Syarat 3: Konfirmasi candle bearish (Close < Open)
        if (curr_high > swing_high) and (curr_close < swing_high) and (curr_close < curr_open):
            penetration = round(curr_high - swing_high, 2)
            upper_wick = round(curr_high - max(curr_open, curr_close), 2)
            return {
                "detected": True,
                "type": "BEARISH",
                "swing_high": swing_high,
                "swing_low": swing_low,
                "penetration": penetration,
                "rejection_wick": upper_wick,
                "reason": (
                    f"Bearish Sweep Terkonfirmasi! High (${curr_high:,.2f}) menyapu Swing High (${swing_high:,.2f}), "
                    f"rejection ditutup di bawah swing (${curr_close:,.2f}) dengan candle merah"
                )
            }

        # -------------------------------------------------------------
        # 3. TIDAK ADA SWEEP
        # -------------------------------------------------------------
        return {
            "detected": False,
            "type": "NONE",
            "swing_high": swing_high,
            "swing_low": swing_low,
            "penetration": 0.0,
            "rejection_wick": 0.0,
            "reason": "Tidak ada penembusan swing high/low dengan rejection yang valid"
        }
