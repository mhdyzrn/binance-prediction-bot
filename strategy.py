from typing import List, Dict, Any, Optional
import config
from indicators import IndicatorCalculator
from liquidity_sweep import LiquiditySweepDetector

class QuantitativeStrategy:
    """
    Strategi Prediksi Multi-Indikator Kuantitatif untuk BTCUSDT (1m -> 5m Horizon).
    Menggabungkan:
    1. Trend Filter: EMA 20 & EMA 50
    2. Momentum Filter: RSI 14
    3. Liquidity Sweep: Swing High/Low 20
    4. Volume Filter: Volume SMA 20
    5. Volatility Filter: ATR 14
    6. Extreme Candle Filter & Spread Filter
    """

    def __init__(self, sweep_detector: Optional[LiquiditySweepDetector] = None):
        self.sweep_detector = sweep_detector or LiquiditySweepDetector(lookback_period=config.SWING_LOOKBACK)

    def evaluate_market(
        self,
        closed_candles: List[Dict[str, Any]],
        current_spread: float = 0.5,
        in_cooldown: bool = False
    ) -> Dict[str, Any]:
        """
        Mengevaluasi seluruh kondisi pasar secara kuantitatif berdasarkan candle yang sudah selesai/tertutup.

        Args:
            closed_candles: List candle 1m yang sudah selesai/ditutup (minimal 55 candle untuk EMA 50).
            current_spread: Spread bid-ask saat ini dalam USDT.
            in_cooldown: Apakah bot sedang dalam masa jeda posisi 5m aktif.

        Returns:
            Dict hasil evaluasi lengkap dan alasan teknikal.
        """
        min_required_candles = max(config.EMA_SLOW_PERIOD + 5, config.SWING_LOOKBACK + 5)
        if not closed_candles or len(closed_candles) < min_required_candles:
            return {
                "prediction": "NEUTRAL",
                "direction": None,
                "score": 0.0,
                "reason": f"Data candle belum mencukupi (diperlukan minimal {min_required_candles} candle)",
                "metrics": {}
            }

        # -------------------------------------------------------------
        # 0. SAFEGUARD: COOLDOWN & SPREAD
        # -------------------------------------------------------------
        if in_cooldown:
            return {
                "prediction": "NEUTRAL",
                "direction": None,
                "score": 0.0,
                "reason": "Sedang dalam masa Cooldown (menunggu evaluasi posisi 5m selesai)",
                "metrics": {}
            }

        if current_spread > config.MAX_SPREAD_USDT:
            return {
                "prediction": "NEUTRAL",
                "direction": None,
                "score": 0.0,
                "reason": f"Spread melebar (${current_spread:.2f} > batas ${config.MAX_SPREAD_USDT:.2f})",
                "metrics": {"spread": current_spread}
            }

        # Ambil deret harga candle yang sudah ditutup
        closes = [float(c["close"]) for c in closed_candles]
        highs = [float(c["high"]) for c in closed_candles]
        lows = [float(c["low"]) for c in closed_candles]
        volumes = [float(c["volume"]) for c in closed_candles]
        signal_candle = closed_candles[-1]
        last_close = closes[-1]

        # -------------------------------------------------------------
        # 1. PERHITUNGAN INDIKATOR KUANTITATIF
        # -------------------------------------------------------------
        ema20 = IndicatorCalculator.calculate_ema(closes, config.EMA_FAST_PERIOD)
        ema50 = IndicatorCalculator.calculate_ema(closes, config.EMA_SLOW_PERIOD)
        rsi14 = IndicatorCalculator.calculate_rsi(closes, config.RSI_PERIOD)
        atr14 = IndicatorCalculator.calculate_atr(highs, lows, closes, config.ATR_PERIOD)
        vol_sma20 = IndicatorCalculator.calculate_volume_sma(volumes[:-1], config.VOLUME_LOOKBACK)
        signal_vol = volumes[-1]
        c_metrics = IndicatorCalculator.calculate_candle_metrics(signal_candle)
        sweep_res = self.sweep_detector.detect_sweep(closed_candles)

        metrics = {
            "close": last_close,
            "ema20": ema20,
            "ema50": ema50,
            "rsi14": rsi14,
            "atr14": atr14,
            "signal_vol": signal_vol,
            "vol_sma20": vol_sma20,
            "candle_body": c_metrics["body"],
            "sweep_type": sweep_res["type"],
            "sweep_detected": sweep_res["detected"],
            "spread": current_spread
        }

        # Validasi ketersediaan indikator
        if ema20 is None or ema50 is None or rsi14 is None or atr14 is None:
            return {
                "prediction": "NEUTRAL",
                "direction": None,
                "score": 0.0,
                "reason": "Gagal menghitung nilai indikator (riwayat tidak cukup)",
                "metrics": metrics
            }

        # -------------------------------------------------------------
        # 2. FILTER VOLATILITAS (ATR 14)
        # -------------------------------------------------------------
        if atr14 < config.MIN_ATR_THRESHOLD:
            return {
                "prediction": "NEUTRAL",
                "direction": None,
                "score": 0.0,
                "reason": f"Volatilitas terlalu rendah (ATR {atr14:.2f} < ${config.MIN_ATR_THRESHOLD:.2f}) - tidak cukup menutup biaya",
                "metrics": metrics
            }

        # -------------------------------------------------------------
        # 3. FILTER CANDLE EKSTREM
        # -------------------------------------------------------------
        max_allowed_body = config.MAX_CANDLE_BODY_ATR_MULT * atr14
        if c_metrics["body"] > max_allowed_body:
            return {
                "prediction": "NEUTRAL",
                "direction": None,
                "score": 0.0,
                "reason": f"Candle sinyal bergerak terlalu jauh (Body ${c_metrics['body']:.2f} > {config.MAX_CANDLE_BODY_ATR_MULT:.1f}x ATR ${max_allowed_body:.2f})",
                "metrics": metrics
            }

        # -------------------------------------------------------------
        # 4. TREND FILTER (EMA 20 & EMA 50)
        # -------------------------------------------------------------
        ema_diff = ema20 - ema50
        is_sideways = abs(ema_diff) < config.EMA_SIDEWAYS_THRESHOLD
        ema_bullish = (ema_diff >= config.EMA_SIDEWAYS_THRESHOLD)
        ema_bearish = (ema_diff <= -config.EMA_SIDEWAYS_THRESHOLD)

        # -------------------------------------------------------------
        # 5. MOMENTUM FILTER (RSI 14)
        # -------------------------------------------------------------
        rsi_bullish = (config.RSI_BUY_MIN < rsi14 < config.RSI_BUY_MAX)
        rsi_bearish = (config.RSI_SELL_MIN < rsi14 < config.RSI_SELL_MAX)

        # -------------------------------------------------------------
        # 6. VOLUME FILTER
        # -------------------------------------------------------------
        vol_valid = True
        if config.ENABLE_VOLUME_FILTER and vol_sma20 is not None:
            vol_valid = (signal_vol > vol_sma20)

        # -------------------------------------------------------------
        # 7. EVALUASI SINYAL UP (BULLISH)
        # -------------------------------------------------------------
        if sweep_res["type"] == "BULLISH":
            score = 0
            fail_reasons = []

            # Bobot Sweep: 35 poin
            score += 35

            # Bobot Trend: 25 poin
            if ema_bullish:
                score += 25
            elif is_sideways:
                score += 10
            else:
                fail_reasons.append("EMA Bearish (EMA20 < EMA50)")

            # Bobot Momentum: 25 poin
            if rsi_bullish:
                score += 25
            else:
                fail_reasons.append(f"RSI {rsi14:.1f} di luar zona aman ({config.RSI_BUY_MIN:.0f}-{config.RSI_BUY_MAX:.0f})")

            # Bobot Volume: 15 poin
            if vol_valid:
                score += 15
            else:
                fail_reasons.append(f"Volume di bawah rata-rata ({signal_vol:.1f} < {vol_sma20:.1f})")

            if score >= 75:
                return {
                    "prediction": "UP",
                    "direction": "UP",
                    "score": score,
                    "reason": f"Konfirmasi Bullish Sweep + Trend EMA + RSI ({rsi14:.1f})",
                    "metrics": metrics
                }
            else:
                return {
                    "prediction": "NEUTRAL",
                    "direction": None,
                    "score": score,
                    "reason": "Bullish sweep terdeteksi namun filter konfirmasi belum terpenuhi: " + ", ".join(fail_reasons),
                    "metrics": metrics
                }

        # -------------------------------------------------------------
        # 8. EVALUASI SINYAL DOWN (BEARISH)
        # -------------------------------------------------------------
        if sweep_res["type"] == "BEARISH":
            score = 0
            fail_reasons = []

            # Bobot Sweep: 35 poin
            score += 35

            # Bobot Trend: 25 poin
            if ema_bearish:
                score += 25
            elif is_sideways:
                score += 10
            else:
                fail_reasons.append("EMA Bullish (EMA20 > EMA50)")

            # Bobot Momentum: 25 poin
            if rsi_bearish:
                score += 25
            else:
                fail_reasons.append(f"RSI {rsi14:.1f} di luar zona aman ({config.RSI_SELL_MIN:.0f}-{config.RSI_SELL_MAX:.0f})")

            # Bobot Volume: 15 poin
            if vol_valid:
                score += 15
            else:
                fail_reasons.append(f"Volume di bawah rata-rata ({signal_vol:.1f} < {vol_sma20:.1f})")

            if score >= 75:
                return {
                    "prediction": "DOWN",
                    "direction": "DOWN",
                    "score": score,
                    "reason": f"Konfirmasi Bearish Sweep + Trend EMA + RSI ({rsi14:.1f})",
                    "metrics": metrics
                }
            else:
                return {
                    "prediction": "NEUTRAL",
                    "direction": None,
                    "score": score,
                    "reason": "Bearish sweep terdeteksi namun filter konfirmasi belum terpenuhi: " + ", ".join(fail_reasons),
                    "metrics": metrics
                }

        # -------------------------------------------------------------
        # 9. TIDAK ADA SINYAL KUAT (NEUTRAL)
        # -------------------------------------------------------------
        reason_neutral = "Tidak ada konfirmasi liquidity sweep pada level swing 20 candle."
        if is_sideways:
            reason_neutral = "Pasar Sideways (EMA20 & EMA50 berdempetan) & tidak ada liquidity sweep."

        return {
            "prediction": "NEUTRAL",
            "direction": None,
            "score": 0.0,
            "reason": reason_neutral,
            "metrics": metrics
        }
