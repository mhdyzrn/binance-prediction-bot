import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from typing import List, Dict, Any, Optional, Tuple
import config

class BinanceFuturesClient:
    """
    Client REST API Binance Futures USDT-M (Mainnet & Testnet).
    Mendukung pengambilan data kline publik, orderbook spread,
    serta eksekusi aman bertingkat (SIGNAL_ONLY, TESTNET, LIVE).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.api_key = api_key or config.BINANCE_API_KEY
        self.api_secret = api_secret or config.BINANCE_API_SECRET
        self.base_url = base_url or config.BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "BtcPredictionBot/1.0 (Termux/Linux)",
            "Content-Type": "application/x-www-form-urlencoded"
        })
        self.time_offset: int = 0
        self._sync_server_time()

    def _sync_server_time(self) -> None:
        """Menghitung perbedaan waktu antara perangkat lokal dan server Binance"""
        try:
            resp = self.session.get(f"{self.base_url}/fapi/v1/time", timeout=(2.0, 3.5))
            if resp.status_code == 200:
                server_time = resp.json().get("serverTime")
                local_time = int(time.time() * 1000)
                self.time_offset = local_time - server_time
        except Exception:
            self.time_offset = 0

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Membuat timestamp dan signature HMAC-SHA256 untuk endpoint privat"""
        params["timestamp"] = int(time.time() * 1000) - self.time_offset
        params["recvWindow"] = 10000
        query_str = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def get_klines(
        self,
        symbol: str = config.SYMBOL,
        interval: str = config.ANALYSIS_TIMEFRAME,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Mengambil data candlestick resmi dari Binance Futures USDT-M.
        Setiap candle dipetakan secara rapi menjadi dict typed.
        """
        url = f"{self.base_url}/fapi/v1/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}

        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=(3.0, 5.0))
                if resp.status_code == 200:
                    raw_data = resp.json()
                    candles = []
                    now_ms = time.time() * 1000.0

                    for k in raw_data:
                        # kline Binance: [open_time, open, high, low, close, volume, close_time, quote_vol, trades, ...]
                        open_time_ms = int(k[0])
                        close_time_ms = int(k[6])
                        # Candle dianggap tertutup jika waktu sekarang > close_time
                        is_closed = (now_ms > close_time_ms)

                        candles.append({
                            "open_time": open_time_ms / 1000.0,
                            "open": float(k[1]),
                            "high": float(k[2]),
                            "low": float(k[3]),
                            "close": float(k[4]),
                            "volume": float(k[5]),
                            "close_time": close_time_ms / 1000.0,
                            "is_closed": is_closed
                        })
                    return candles
                elif resp.status_code == 429:
                    time.sleep(1.0 * (attempt + 1))
            except Exception:
                time.sleep(0.5)

        return []

    def get_closed_klines(
        self,
        symbol: str = config.SYMBOL,
        interval: str = config.ANALYSIS_TIMEFRAME,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Mengambil HANYA candle yang sudah tertutup sempurna.
        Mencegah look-ahead bias dan sinyal palsu dari candle yang masih bergerak.
        """
        all_klines = self.get_klines(symbol, interval, limit=limit + 2)
        if not all_klines:
            return []

        # Ambil candle yang is_closed == True, atau jika candle terakhir belum tertutup buang candle terakhir
        closed = [c for c in all_klines if c["is_closed"]]
        if not closed and len(all_klines) > 1:
            closed = all_klines[:-1]

        return closed[-limit:]

    def get_order_book_spread(self, symbol: str = config.SYMBOL) -> Tuple[float, float, float]:
        """
        Mengambil bid price, ask price, dan spread aktual di Binance Futures.
        Returns: (bid, ask, spread_in_usdt)
        """
        url = f"{self.base_url}/fapi/v1/ticker/bookTicker"
        params = {"symbol": symbol}
        try:
            resp = self.session.get(url, params=params, timeout=(2.0, 3.5))
            if resp.status_code == 200:
                data = resp.json()
                bid = float(data.get("bidPrice", 0.0))
                ask = float(data.get("askPrice", 0.0))
                spread = round(max(0.0, ask - bid), 2)
                return bid, ask, spread
        except Exception:
            pass
        return 0.0, 0.0, 0.0

    def test_connection(self) -> Tuple[bool, str, float]:
        """Menguji koneksi ke endpoint Binance Futures dan membaca harga terakhir"""
        url = f"{self.base_url}/fapi/v1/ticker/price"
        params = {"symbol": config.SYMBOL}
        try:
            resp = self.session.get(url, params=params, timeout=(2.5, 4.0))
            if resp.status_code == 200:
                data = resp.json()
                price = float(data.get("price", 0.0))
                return True, "Koneksi Binance Futures Berhasil", price
            return False, f"Server Error HTTP {resp.status_code}", 0.0
        except Exception as e:
            return False, f"Koneksi Gagal: {e}", 0.0

    def get_account_balance(self) -> float:
        """Mengambil saldo USDT akun Futures (Hanya untuk TESTNET atau LIVE)"""
        if config.TRADING_MODE == "SIGNAL_ONLY":
            return 0.0
        if not self.api_key or not self.api_secret:
            return 0.0

        url = f"{self.base_url}/fapi/v2/balance"
        headers = {"X-MBX-APIKEY": self.api_key}
        params = self._sign({})

        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=(3.0, 5.0))
            if resp.status_code == 200:
                for b in resp.json():
                    if b.get("asset") == "USDT":
                        return float(b.get("availableBalance", 0.0))
        except Exception:
            pass
        return 0.0
