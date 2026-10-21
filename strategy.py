from typing import Dict, Any
import config

class PredictionStrategy:
    """
    Strategi Momentum Trend-Rider khusus pasar BTC 5 Menit:
    - Fase 1 (Sisa waktu > 02:30): Mengamati pembentukan tren awal ronde.
    - Fase 2 (Sisa waktu 02:30 s.d 00:45): Jendela Momentum Eksekusi saat pool Web3
      masih menawarkan payout tebal (minimal 1.25x s.d 2.20x / profit +$0.25 s.d +$1.20).
    - Fase 3 (Sisa waktu < 00:45): Batas akhir eksekusi (menghindari payout menyusut / gepeng).
    """
    def __init__(self):
        self.trigger_sec = config.SNIPER_TRIGGER_SECONDS
        self.deadline_sec = config.SNIPER_DEADLINE_SECONDS
        self.min_diff = config.SNIPER_MIN_DIFF
        self.min_payout = getattr(config, "MIN_PAYOUT_MULTIPLIER", 1.25)
        self.max_payout = getattr(config, "MAX_PAYOUT_MULTIPLIER", 2.20)

    def evaluate_signal(self, market: Dict[str, Any]) -> Dict[str, Any]:
        seconds_left = market["seconds_left"]
        diff_val = market["diff_val"]

        # Safeguard 1: Proteksi Cooldown setelah kekalahan beruntun
        if market.get("in_cooldown", False):
            rounds_left = market.get("cooldown_rounds_left", 1)
            return {
                "action": "OBSERVE",
                "direction": None,
                "reason": f"Proteksi Cooldown aktif ({rounds_left} ronde jeda setelah {config.MAX_CONSECUTIVE_LOSS}x loss)"
            }

        # Safeguard 2: Jika koneksi terputus atau data harga basi (> 5 detik)
        if not market.get("is_online", True) or market.get("stale_seconds", 0) > 5:
            stale = market.get("stale_seconds", 0)
            return {
                "action": "OBSERVE",
                "direction": None,
                "reason": f"Koneksi terputus! Order ditahan ({stale}s)"
            }

        # Fase 1: Mengamati (Belum masuk jendela momentum)
        if seconds_left > self.trigger_sec:
            mins_wait = (seconds_left - self.trigger_sec) // 60
            secs_wait = (seconds_left - self.trigger_sec) % 60
            return {
                "action": "OBSERVE",
                "direction": None,
                "reason": f"Mengamati tren (Momentum aktif dalam {mins_wait:02d}:{secs_wait:02d})"
            }

        # Fase 3: Batas akhir jendela momentum (< 45 detik, payout sudah menyusut)
        if seconds_left < self.deadline_sec:
            return {
                "action": "EXPIRED_SOON",
                "direction": None,
                "reason": "Jendela momentum terlewati (Sisa waktu < 00:45)"
            }

        # Fase 2: Jendela Eksekusi Momentum Aktif (02:30 s.d 00:45)
        rsi = market.get("rsi")
        rsi_str = f"{rsi:.1f}" if rsi is not None else "-"
        candle_color = market.get("candle_color", "NEUTRAL")
        candle_change = market.get("candle_change", 0.0)
        tendency_bias = market.get("tendency_bias", "")
        tendency_stat = market.get("tendency_stat", "")
        min_strong_diff = getattr(config, "MIN_STRONG_BIAS_DIFF", 20.0)
        ema_trend = market.get("ema_trend", "NETRAL")
        dist_res = market.get("dist_resistance")
        dist_sup = market.get("dist_support")
        sr_buffer = getattr(config, "SR_BUFFER_USD", 8.0)

        # Kasus A: Spot BTC unggul di atas target strike (Potensi NAIK)
        if diff_val >= self.min_diff:
            payout = market.get("payout_naik", 1.0)

            # Filter 1: Payout Minimum (Tolak payout receh < 1.25x demi rasio profit sehat)
            if payout < self.min_payout:
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Payout NAIK rendah ({payout:.2f}x < {self.min_payout:.2f}x) - Tahan order"
                }

            # Filter 2: Payout Maksimum (Hindari taruhan probabilitas terlalu kecil > 2.20x)
            if payout > self.max_payout:
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Payout NAIK ekstrim ({payout:.2f}x > {self.max_payout:.2f}x) - Probabilitas tipis"
                }

            # Filter 3: RSI Jenuh Beli (Cegah beli di pucuk overbought)
            if rsi is not None and rsi > getattr(config, "RSI_OVERBOUGHT", 75.0):
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Filter RSI Jenuh Beli ({rsi_str} > {config.RSI_OVERBOUGHT:.0f}) - Tahan NAIK"
                }

            # Filter 4: RSI Momentum Minimum (Pastikan ada dorongan bullish RSI >= 48)
            if rsi is not None and rsi < getattr(config, "RSI_MIN_NAIK", 48.0):
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Momentum NAIK lemah (RSI {rsi_str} < {config.RSI_MIN_NAIK:.0f}) - Tahan NAIK"
                }

            # Filter 5: Micro-Momentum Candle 1M (Cegah masuk NAIK saat candle sedang terjun tajam)
            if candle_color == "RED" and candle_change < -12.0:
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Candle 1m koreksi turun tajam (-${abs(candle_change):.1f}) - Tahan NAIK"
                }

            # Filter 6: Trend Alignment (Cegah beli NAIK dengan selisih tipis saat bias pasar BEARISH KUAT)
            if "BEARISH (KUAT)" in tendency_bias and diff_val < min_strong_diff:
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Bias pasar BEARISH KUAT ({tendency_stat}) - Tahan NAIK (Butuh selisih >${min_strong_diff:.0f})"
                }

            # Filter 7: EMA Trend Filter (Cegah beli NAIK jika tren grafik EMA Bearish 9 < 21)
            if ema_trend == "BEARISH":
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": "Chart Melawan Tren: EMA Bearish (9 < 21) - Tahan NAIK"
                }

            # Filter 8: Resistance Wall Guard (Cegah beli NAIK tepat di pucuk resistance)
            if dist_res is not None and 0 <= dist_res < sr_buffer:
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Chart Mentok Resistance (${market.get('resistance', 0):,.1f}, sisa ${dist_res:.1f}) - Tahan NAIK rawan mantul"
                }

            return {
                "action": "ENTER",
                "direction": "Naik",
                "payout": payout,
                "reason": f"Momentum NAIK Kuat! Spot (+${diff_val:,.1f}) | Payout: {payout:.2f}x | RSI: {rsi_str} | EMA: {ema_trend}"
            }

        # Kasus B: Spot BTC unggul di bawah target strike (Potensi TURUN)
        elif diff_val <= -self.min_diff:
            payout = market.get("payout_turun", 1.0)

            # Filter 1: Payout Minimum (Tolak payout receh < 1.25x demi rasio profit sehat)
            if payout < self.min_payout:
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Payout TURUN rendah ({payout:.2f}x < {self.min_payout:.2f}x) - Tahan order"
                }

            # Filter 2: Payout Maksimum (Hindari taruhan probabilitas terlalu kecil > 2.20x)
            if payout > self.max_payout:
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Payout TURUN ekstrim ({payout:.2f}x > {self.max_payout:.2f}x) - Probabilitas tipis"
                }

            # Filter 3: RSI Jenuh Jual (Cegah jual di dasar oversold)
            if rsi is not None and rsi < getattr(config, "RSI_OVERSOLD", 25.0):
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Filter RSI Jenuh Jual ({rsi_str} < {config.RSI_OVERSOLD:.0f}) - Tahan TURUN"
                }

            # Filter 4: RSI Momentum Maksimum (Pastikan ada dorongan bearish RSI <= 52)
            if rsi is not None and rsi > getattr(config, "RSI_MAX_TURUN", 52.0):
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Momentum TURUN lemah (RSI {rsi_str} > {config.RSI_MAX_TURUN:.0f}) - Tahan TURUN"
                }

            # Filter 5: Micro-Momentum Candle 1M (Cegah masuk TURUN saat candle sedang memantul naik)
            if candle_color == "GREEN" and candle_change > 12.0:
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Candle 1m pantulan naik tajam (+${candle_change:.1f}) - Tahan TURUN"
                }

            # Filter 6: Trend Alignment (Cegah beli TURUN dengan selisih tipis saat bias pasar BULLISH KUAT)
            if "BULLISH (KUAT)" in tendency_bias and abs(diff_val) < min_strong_diff:
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Bias pasar BULLISH KUAT ({tendency_stat}) - Tahan TURUN (Butuh selisih >${min_strong_diff:.0f})"
                }

            # Filter 7: EMA Trend Filter (Cegah beli TURUN jika tren grafik EMA Bullish 9 > 21)
            if ema_trend == "BULLISH":
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": "Chart Melawan Tren: EMA Bullish (9 > 21) - Tahan TURUN"
                }

            # Filter 8: Support Floor Guard (Cegah beli TURUN tepat di dasar support)
            if dist_sup is not None and 0 <= dist_sup < sr_buffer:
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Chart Mentok Support (${market.get('support', 0):,.1f}, sisa ${dist_sup:.1f}) - Tahan TURUN rawan mantul"
                }

            return {
                "action": "ENTER",
                "direction": "Turun",
                "payout": payout,
                "reason": f"Momentum TURUN Kuat! Spot (-${abs(diff_val):,.1f}) | Payout: {payout:.2f}x | RSI: {rsi_str} | EMA: {ema_trend}"
            }

        # Kasus C: Selisih tipis di bawah MIN_DIFF (< $15)
        else:
            return {
                "action": "OBSERVE",
                "direction": None,
                "reason": f"Selisih tipis (${abs(diff_val):,.2f} < ${self.min_diff:.0f}) - Menahan order"
            }
