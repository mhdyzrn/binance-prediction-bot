import math
from typing import List, Dict, Any, Optional

class IndicatorCalculator:
    """
    Kalkulator Indikator Kuantitatif Mandiri (Pure Python)
    Dirancang ringan, cepat, presisi tinggi, dan berjalan mulus di Termux Android & Linux
    tanpa dependensi eksternal C-compiler.
    """

    @staticmethod
    def calculate_ema(closes: List[float], period: int) -> Optional[float]:
        """
        Menghitung Exponential Moving Average (EMA) pada candle terakhir yang ditutup.
        Rumus: k = 2 / (period + 1)
        EMA_t = (Close_t * k) + (EMA_{t-1} * (1 - k))
        """
        if not closes or len(closes) < period:
            return None

        k = 2.0 / (period + 1.0)
        # Inisialisasi awal dengan Simple Moving Average (SMA)
        ema = sum(closes[:period]) / float(period)

        for price in closes[period:]:
            ema = (price * k) + (ema * (1.0 - k))

        return round(ema, 4)

    @staticmethod
    def calculate_ema_series(closes: List[float], period: int) -> List[Optional[float]]:
        """Menghitung seluruh deret waktu EMA untuk keperluan backtesting"""
        if not closes:
            return []

        k = 2.0 / (period + 1.0)
        series: List[Optional[float]] = [None] * len(closes)

        if len(closes) < period:
            return series

        sma = sum(closes[:period]) / float(period)
        series[period - 1] = sma
        prev_ema = sma

        for i in range(period, len(closes)):
            curr_ema = (closes[i] * k) + (prev_ema * (1.0 - k))
            series[i] = curr_ema
            prev_ema = curr_ema

        return series

    @staticmethod
    def calculate_rsi(closes: List[float], period: int = 14) -> Optional[float]:
        """
        Menghitung Relative Strength Index (RSI) periode 14 dengan metode Wilder's Smoothing.
        """
        if not closes or len(closes) < period + 1:
            return None

        gains = []
        losses = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            if diff >= 0:
                gains.append(diff)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(diff))

        if len(gains) < period:
            return None

        # Rata-rata awal (SMA)
        avg_gain = sum(gains[:period]) / float(period)
        avg_loss = sum(losses[:period]) / float(period)

        # Wilder's smoothing untuk data selanjutnya
        for i in range(period, len(gains)):
            avg_gain = ((avg_gain * (period - 1)) + gains[i]) / float(period)
            avg_loss = ((avg_loss * (period - 1)) + losses[i]) / float(period)

        if avg_loss == 0.0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return round(rsi, 2)

    @staticmethod
    def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
        """
        Menghitung Average True Range (ATR) periode 14.
        True Range (TR) = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
        """
        n = len(closes)
        if n < period + 1 or len(highs) < n or len(lows) < n:
            return None

        tr_list = []
        for i in range(1, n):
            h_l = highs[i] - lows[i]
            h_pc = abs(highs[i] - closes[i - 1])
            l_pc = abs(lows[i] - closes[i - 1])
            tr = max(h_l, h_pc, l_pc)
            tr_list.append(tr)

        if len(tr_list) < period:
            return None

        # Wilder's Smoothing ATR
        atr = sum(tr_list[:period]) / float(period)
        for i in range(period, len(tr_list)):
            atr = ((atr * (period - 1)) + tr_list[i]) / float(period)

        return round(atr, 4)

    @staticmethod
    def calculate_volume_sma(volumes: List[float], period: int = 20) -> Optional[float]:
        """Menghitung rata-rata volume (SMA) periode 20"""
        if not volumes or len(volumes) < period:
            return None
        return round(sum(volumes[-period:]) / float(period), 4)

    @staticmethod
    def calculate_candle_metrics(candle: Dict[str, Any]) -> Dict[str, float]:
        """Menghitung metrik anatomi candle: body, upper shadow, lower shadow, total range"""
        c_open = float(candle["open"])
        c_high = float(candle["high"])
        c_low = float(candle["low"])
        c_close = float(candle["close"])

        body = abs(c_close - c_open)
        total_range = c_high - c_low
        is_bullish = c_close >= c_open

        if is_bullish:
            upper_shadow = c_high - c_close
            lower_shadow = c_open - c_low
        else:
            upper_shadow = c_high - c_open
            lower_shadow = c_close - c_low

        return {
            "body": round(body, 4),
            "range": round(total_range, 4),
            "upper_shadow": round(upper_shadow, 4),
            "lower_shadow": round(lower_shadow, 4),
            "is_bullish": 1.0 if is_bullish else 0.0
        }
