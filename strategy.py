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

        # Safeguard: Jika koneksi terputus atau data harga basi (> 5 detik)
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
        # Untuk BTC, jika selisih harga >= $10.0
        if diff_val >= self.min_diff:
            return {
                "action": "ENTER",
                "direction": "Naik",
                "payout": market["payout_naik"],
                "reason": f"Sniper NAIK! Spot BTC unggul di atas target (+${diff_val:,.2f})"
            }
        elif diff_val <= -self.min_diff:
            return {
                "action": "ENTER",
                "direction": "Turun",
                "payout": market["payout_turun"],
                "reason": f"Sniper TURUN! Spot BTC unggul di bawah target (-${abs(diff_val):,.2f})"
            }
        else:
            # Jika selisih tipis (< $10), ikuti arah harga dominan
            if diff_val >= 0:
                dir_choice = "Naik"
                payout = market["payout_naik"]
            else:
                dir_choice = "Turun"
                payout = market["payout_turun"]

            return {
                "action": "ENTER",
                "direction": dir_choice,
                "payout": payout,
                "reason": f"Sniper Konfirmasi Tipis: Ambil {dir_choice}"
            }
