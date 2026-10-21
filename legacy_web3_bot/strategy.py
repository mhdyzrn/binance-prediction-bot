from typing import Dict, Any
import config

class PredictionStrategy:
    """
    Strategi Momentum RSI & Chart Synchronizer khusus pasar BTC 5 Menit:
    - Filter Payout: Dinonaktifkan (ENABLE_PAYOUT_FILTER = False).
    - Sinyal NAIK: Jika RSI Bullish DAN Chart Bullish -> LANGSUNG ENTRY NAIK.
    - Sinyal TURUN: Jika RSI Bearish DAN Chart Bearish -> LANGSUNG ENTRY TURUN.
    - Jendela Eksekusi: Sisa waktu 03:30 s.d 00:15 ronde berjalan.
    """
    def __init__(self):
        self.trigger_sec = getattr(config, "SNIPER_TRIGGER_SECONDS", 210)
        self.deadline_sec = getattr(config, "SNIPER_DEADLINE_SECONDS", 15)
        self.min_diff = getattr(config, "SNIPER_MIN_DIFF", 5.0)
        self.enable_payout_filter = getattr(config, "ENABLE_PAYOUT_FILTER", False)
        self.min_payout = getattr(config, "MIN_PAYOUT_MULTIPLIER", 1.25)
        self.max_payout = getattr(config, "MAX_PAYOUT_MULTIPLIER", 2.20)
        self.rsi_bull_thresh = getattr(config, "RSI_BULLISH_THRESHOLD", 48.0)
        self.rsi_bear_thresh = getattr(config, "RSI_BEARISH_THRESHOLD", 52.0)

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

        # Fase 1: Mengamati (Belum masuk jendela evaluasi ronde)
        if seconds_left > self.trigger_sec:
            mins_wait = (seconds_left - self.trigger_sec) // 60
            secs_wait = (seconds_left - self.trigger_sec) % 60
            return {
                "action": "OBSERVE",
                "direction": None,
                "reason": f"Mengamati tren awal (Evaluasi aktif dalam {mins_wait:02d}:{secs_wait:02d})"
            }

        # Fase 3: Batas akhir jendela ronde (< 15 detik)
        if seconds_left < self.deadline_sec:
            return {
                "action": "EXPIRED_SOON",
                "direction": None,
                "reason": f"Sisa waktu ronde habis (< {self.deadline_sec}s)"
            }

        # Fase 2: Evaluasi Sinkronisasi RSI & Chart
        rsi = market.get("rsi")
        rsi_str = f"{rsi:.1f}" if rsi is not None else "-"
        candle_color = market.get("candle_color", "NEUTRAL")
        candle_change = market.get("candle_change", 0.0)
        ema_trend = market.get("ema_trend", "NETRAL")
        payout_naik = market.get("payout_naik", 1.0)
        payout_turun = market.get("payout_turun", 1.0)

        # Evaluasi Status RSI:
        # Bullish jika RSI >= 48 (atau >= 50)
        # Bearish jika RSI <= 52 (atau <= 50)
        rsi_bullish = (rsi is not None and rsi >= self.rsi_bull_thresh)
        rsi_bearish = (rsi is not None and rsi <= self.rsi_bear_thresh)

        # Evaluasi Status Chart:
        # Chart Bullish: Spot unggul di atas Strike (>= min_diff) DAN didukung candle hijau atau EMA bullish atau leading kuat
        chart_bullish = (diff_val >= self.min_diff) and (candle_color == "GREEN" or ema_trend == "BULLISH" or diff_val >= 15.0)

        # Chart Bearish: Spot tertekan di bawah Strike (<= -min_diff) DAN didukung candle merah atau EMA bearish atau leading kuat
        chart_bearish = (diff_val <= -self.min_diff) and (candle_color == "RED" or ema_trend == "BEARISH" or abs(diff_val) >= 15.0)

        # ----------------------------------------------------
        # KASUS 1: RSI BULLISH & CHART BULLISH -> LANGSUNG ENTRY NAIK
        # ----------------------------------------------------
        if rsi_bullish and chart_bullish:
            # Filter Payout (Hanya jika diaktifkan manual)
            if self.enable_payout_filter:
                if payout_naik < self.min_payout:
                    return {
                        "action": "OBSERVE",
                        "direction": None,
                        "reason": f"Payout NAIK rendah ({payout_naik:.2f}x < {self.min_payout:.2f}x) - Tahan order"
                    }
                if payout_naik > self.max_payout:
                    return {
                        "action": "OBSERVE",
                        "direction": None,
                        "reason": f"Payout NAIK ekstrim ({payout_naik:.2f}x > {self.max_payout:.2f}x) - Tahan order"
                    }

            return {
                "action": "ENTER",
                "direction": "Naik",
                "payout": payout_naik,
                "reason": f"RSI & Chart SINKRON BULLISH! Spot (+${diff_val:,.1f}) | RSI: {rsi_str} | Candle: {candle_color} | EMA: {ema_trend} | Payout: {payout_naik:.2f}x"
            }

        # ----------------------------------------------------
        # KASUS 2: RSI BEARISH & CHART BEARISH -> LANGSUNG ENTRY TURUN
        # ----------------------------------------------------
        if rsi_bearish and chart_bearish:
            # Filter Payout (Hanya jika diaktifkan manual)
            if self.enable_payout_filter:
                if payout_turun < self.min_payout:
                    return {
                        "action": "OBSERVE",
                        "direction": None,
                        "reason": f"Payout TURUN rendah ({payout_turun:.2f}x < {self.min_payout:.2f}x) - Tahan order"
                    }
                if payout_turun > self.max_payout:
                    return {
                        "action": "OBSERVE",
                        "direction": None,
                        "reason": f"Payout TURUN ekstrim ({payout_turun:.2f}x > {self.max_payout:.2f}x) - Tahan order"
                    }

            return {
                "action": "ENTER",
                "direction": "Turun",
                "payout": payout_turun,
                "reason": f"RSI & Chart SINKRON BEARISH! Spot (-${abs(diff_val):,.1f}) | RSI: {rsi_str} | Candle: {candle_color} | EMA: {ema_trend} | Payout: {payout_turun:.2f}x"
            }

        # ----------------------------------------------------
        # KASUS 3: BELUM SINKRON (RSI dan Chart saling berlawanan atau selisih tipis)
        # ----------------------------------------------------
        if abs(diff_val) < self.min_diff:
            return {
                "action": "OBSERVE",
                "direction": None,
                "reason": f"Selisih harga tipis (${abs(diff_val):,.2f} < ${self.min_diff:.0f}) - Menunggu arah chart tegas"
            }

        if diff_val >= self.min_diff and not rsi_bullish:
            return {
                "action": "OBSERVE",
                "direction": None,
                "reason": f"Chart Naik (+${diff_val:.1f}) tapi RSI Bearish ({rsi_str} < {self.rsi_bull_thresh:.0f}) - Menunggu sinkron"
            }

        if diff_val <= -self.min_diff and not rsi_bearish:
            return {
                "action": "OBSERVE",
                "direction": None,
                "reason": f"Chart Turun (-${abs(diff_val):.1f}) tapi RSI Bullish ({rsi_str} > {self.rsi_bear_thresh:.0f}) - Menunggu sinkron"
            }

        return {
            "action": "OBSERVE",
            "direction": None,
            "reason": f"Menunggu keselarasan RSI ({rsi_str}) dan Chart ({candle_color}, {ema_trend})"
        }
