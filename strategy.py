from typing import Dict, Any
import config

class PredictionStrategy:
    """
    Strategi Late-Sniper khusus pasar BTC 5 Menit:
    - Selama 3.5 menit pertama (Hitung mundur > 01:15): Bot memantau pergerakan harga BTC
    - Di sisa 75 detik terakhir (01:15 s.d 00:10): Jendela Sniper mengeksekusi order riil
      berdasarkan posisi harga spot BTC terhadap target strike.
    """
    def __init__(self):
        self.trigger_sec = config.SNIPER_TRIGGER_SECONDS
        self.deadline_sec = config.SNIPER_DEADLINE_SECONDS
        self.min_diff = config.SNIPER_MIN_DIFF

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

        # Fase 1: Mengamati (Belum masuk jendela sniper)
        if seconds_left > self.trigger_sec:
            mins_wait = (seconds_left - self.trigger_sec) // 60
            secs_wait = (seconds_left - self.trigger_sec) % 60
            return {
                "action": "OBSERVE",
                "direction": None,
                "reason": f"Mengamati tren (Sniper aktif dalam {mins_wait:02d}:{secs_wait:02d})"
            }

        # Fase 2: Batas akhir jendela taruhan (< 10 detik)
        if seconds_left < self.deadline_sec:
            return {
                "action": "EXPIRED_SOON",
                "direction": None,
                "reason": "Batas waktu taruhan ronde ini ditutup"
            }

        # Fase 3: Jendela Eksekusi Sniper Aktif (01:15 s.d 00:10)
        rsi = market.get("rsi")
        rsi_str = f"{rsi:.1f}" if rsi is not None else "-"

        # Kasus A: Spot BTC unggul di atas target strike (Potensi NAIK)
        if diff_val >= self.min_diff:
            # Filter RSI: Cegah beli NAIK jika pasar sedang overbought ekstrim (rawan dump/reversal)
            if rsi is not None and rsi >= config.RSI_OVERBOUGHT:
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Filter RSI Jenuh Beli ({rsi_str} > {config.RSI_OVERBOUGHT}) - Tahan NAIK demi proteksi modal"
                }

            return {
                "action": "ENTER",
                "direction": "Naik",
                "payout": market["payout_naik"],
                "reason": f"Sniper NAIK! Spot unggul (+${diff_val:,.2f}) | RSI: {rsi_str}"
            }

        # Kasus B: Spot BTC unggul di bawah target strike (Potensi TURUN)
        elif diff_val <= -self.min_diff:
            # Filter RSI: Cegah beli TURUN jika pasar sedang oversold ekstrim (rawan pump/bounce)
            if rsi is not None and rsi <= config.RSI_OVERSOLD:
                return {
                    "action": "OBSERVE",
                    "direction": None,
                    "reason": f"Filter RSI Jenuh Jual ({rsi_str} < {config.RSI_OVERSOLD}) - Tahan TURUN demi proteksi modal"
                }

            return {
                "action": "ENTER",
                "direction": "Turun",
                "payout": market["payout_turun"],
                "reason": f"Sniper TURUN! Spot unggul (-${abs(diff_val):,.2f}) | RSI: {rsi_str}"
            }

        # Kasus C: Selisih tipis di bawah MIN_DIFF (< $15)
        # SANGAT KRUSIAL UNTUK MODAL $10: TAHAN DIRI & JANGAN MEMAKSAKAN ORDER PADA PASAR NOISE!
        else:
            return {
                "action": "OBSERVE",
                "direction": None,
                "reason": f"Selisih tipis (${abs(diff_val):,.2f} < ${self.min_diff:.0f}) - Menahan order demi proteksi modal"
            }

