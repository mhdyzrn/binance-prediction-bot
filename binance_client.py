import time
import hmac
import hashlib
import requests
from datetime import datetime
from urllib.parse import urlencode
from typing import Dict, Any, List, Optional
import config

class BinanceClient:
    """
    Klien Resmi Binance API:
    - Menangani autentikasi HMAC-SHA256 untuk transaksi Real Trading
    - Mengambil data live BTC/USDT langsung dari server Binance
    - Mengecek saldo USDT riil akun Binance
    """
    def __init__(self, api_key: str = config.BINANCE_API_KEY, api_secret: str = config.BINANCE_API_SECRET):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = config.BINANCE_BASE_URL
        self.market_data_url = config.BINANCE_VISION_URL
        self.session = requests.Session()
        if config.BINANCE_PROXY:
            self.session.proxies.update({
                "http": config.BINANCE_PROXY,
                "https": config.BINANCE_PROXY
            })
        self.session.headers.update({
            "User-Agent": "BinancePredictionBot/2.0",
            "Content-Type": "application/x-www-form-urlencoded"
        })
        self._cached_wallet: Optional[Dict[str, str]] = None

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Menghasilkan timestamp & signature HMAC-SHA256 resmi Binance"""
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def get_spot_price(self, symbol: str = config.TARGET_SYMBOL) -> float:
        """
        Mengambil harga spot Bitcoin real-time dengan failover otomatis ke beberapa mirror
        resmi Binance jika salah satu server mengalami gangguan/timeout.
        """
        endpoints = [
            f"{self.market_data_url}/api/v3/ticker/price",
            f"{self.base_url}/api/v3/ticker/price",
            "https://api1.binance.com/api/v3/ticker/price"
        ]

        last_err = None
        for ep in endpoints:
            try:
                resp = self.session.get(ep, params={"symbol": symbol}, timeout=(2.0, 3.0))
                if resp.status_code == 200:
                    data = resp.json()
                    return float(data["price"])
            except Exception as e:
                last_err = e
                continue

        if last_err:
            raise last_err
        raise ConnectionError("Gagal mengambil harga BTC dari semua endpoint mirror Binance")

    def test_account_connection(self) -> tuple[bool, str, float]:
        """
        Menguji koneksi ke Binance API dan mengambil saldo USDT riil.
        Mengembalikan (status_sukses, pesan, saldo_usdt).
        """
        if not self.api_key or not self.api_secret:
            return False, "API Key / Secret belum diisi di file .env", 0.0

        url = f"{self.base_url}/api/v3/account"
        params = self._sign({})
        headers = {"X-MBX-APIKEY": self.api_key}

        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=(3.0, 5.0))
            if resp.status_code == 200:
                data = resp.json()
                for b in data.get("balances", []):
                    if b.get("asset") == "USDT":
                        return True, "Koneksi berhasil", float(b.get("free", 0.0))
                return True, "Koneksi berhasil (USDT 0.00)", 0.0
            else:
                try:
                    err = resp.json().get("msg", resp.text)
                except Exception:
                    err = resp.text
                return False, f"Respon Binance ({resp.status_code}): {err}", 0.0
        except requests.exceptions.ConnectTimeout:
            return False, "Timeout koneksi ke api.binance.com (Diblokir ISP). Aktifkan VPN (misal 1.1.1.1 WARP).", 0.0
        except requests.exceptions.ConnectionError:
            return False, "Gagal koneksi ke api.binance.com (Koneksi ditolak/diblokir ISP). Aktifkan VPN.", 0.0
        except Exception as e:
            return False, f"Error: {e}", 0.0

    def get_real_usdt_balance(self) -> Optional[float]:
        """
        Mengambil saldo USDT riil dari akun Binance
        Menggunakan endpoint resmi GET /api/v3/account
        Mengembalikan None jika jaringan terputus agar tidak menimpa saldo sebelumnya
        """
        if not self.api_key or not self.api_secret:
            return 0.0

        url = f"{self.base_url}/api/v3/account"
        params = self._sign({})
        headers = {"X-MBX-APIKEY": self.api_key}

        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=(3.0, 5.0))
            if resp.status_code == 200:
                data = resp.json()
                for b in data.get("balances", []):
                    if b.get("asset") == "USDT":
                        return float(b.get("free", 0.0))
                return 0.0
            return None
        except Exception:
            return None

    def get_prediction_wallet(self) -> tuple[Optional[Dict[str, str]], Optional[str]]:
        """Mengambil info wallet address & id untuk Web3 Prediction. Mengembalikan (wallet, err_msg)"""
        if self._cached_wallet:
            return self._cached_wallet, None
        url = f"{self.base_url}/sapi/v1/w3w/wallet/prediction/wallet/list"
        params = self._sign({})
        headers = {"X-MBX-APIKEY": self.api_key}
        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=(3.0, 5.0))
            if resp.status_code == 200:
                data = resp.json()
                wallets = data.get("wallets", [])
                if wallets:
                    self._cached_wallet = {
                        "walletAddress": wallets[0].get("walletAddress"),
                        "walletId": wallets[0].get("walletId")
                    }
                    return self._cached_wallet, None
                return None, "Prediction Wallet belum dibuat di akun Binance Anda. Buka menu Prediction di aplikasi Binance."
            return None, f"Respon server Binance ({resp.status_code}): {resp.text[:50]}"
        except requests.exceptions.Timeout:
            return None, "Koneksi timeout saat mengecek wallet Binance (Periksa VPN/Proxy)."
        except requests.exceptions.ConnectionError:
            return None, "Koneksi terputus saat mengecek wallet Binance (Periksa internet/VPN)."
        except Exception as e:
            return None, f"Gagal mengecek wallet: {e}"

    def get_active_btc_prediction_market(self) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Mengambil data pasar BTC 5m resmi dari Binance Web3 Prediction. Mengembalikan (market, err_msg)"""
        url = f"{self.base_url}/sapi/v1/w3w/wallet/prediction/market/list"
        params = self._sign({"limit": 20})
        headers = {"X-MBX-APIKEY": self.api_key}
        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=(3.0, 5.0))
            if resp.status_code == 200:
                data = resp.json()
                for topic in data.get("marketTopics", []):
                    title = topic.get("title", "")
                    if "BTC" in title and "5m" in title:
                        return topic, None
                return None, "Pasar prediksi BTC 5m sedang tidak aktif di server Binance"
            return None, f"Gagal memuat pasar ({resp.status_code})"
        except requests.exceptions.Timeout:
            return None, "Koneksi timeout saat memuat pasar prediksi"
        except requests.exceptions.ConnectionError:
            return None, "Koneksi terputus saat memuat pasar prediksi"
        except Exception as e:
            return None, f"Error pasar: {e}"

    def place_real_prediction_order(self, direction: str, amount_usdt: float, market_id: str = "BTC-5M") -> Dict[str, Any]:
        """
        Mengirimkan pesanan taruhan riil ke Binance Web3 Prediction SAPI
        Flow resmi dengan penanganan gangguan jaringan & timeout:
        1. Ambil walletAddress & walletId
        2. Cari tokenId untuk arah pilihan (Up/Naik atau Down/Turun)
        3. POST /sapi/v1/w3w/wallet/prediction/trade/get-quote
        4. POST /sapi/v1/w3w/wallet/prediction/trade/place-order-bundle
        """
        if not self.api_key or not self.api_secret:
            return {
                "success": False,
                "msg": "API Key / Secret belum diisi di file .env"
            }

        # 1. Ambil wallet info
        wallet, w_err = self.get_prediction_wallet()
        if not wallet or not wallet.get("walletAddress"):
            return {
                "success": False,
                "msg": w_err or "Prediction Wallet tidak ditemukan"
            }

        wallet_addr = wallet["walletAddress"]
        wallet_id = wallet.get("walletId", "")

        # 2. Cari token ID pasar aktif
        market_topic, m_err = self.get_active_btc_prediction_market()
        if not market_topic or not market_topic.get("markets"):
            return {"success": False, "msg": m_err or "Pasar BTC 5m tidak ditemukan"}

        sub_market = market_topic["markets"][0]
        target_name = "Up" if direction == "Naik" else "Down"
        token_id = None
        for outcome in sub_market.get("outcomes", []):
            if outcome.get("name") == target_name:
                token_id = outcome.get("tokenId")
                break

        if not token_id:
            return {"success": False, "msg": f"Token ID untuk arah {direction} tidak ditemukan di pasar"}

        # 3. Dapatkan Quote
        quote_url = f"{self.base_url}/sapi/v1/w3w/wallet/prediction/trade/get-quote"
        amount_wei = str(int(amount_usdt * 1e18))
        q_params = {
            "walletAddress": wallet_addr,
            "tokenId": token_id,
            "side": "BUY",
            "amountIn": amount_wei,
            "orderType": "MARKET",
            "slippageBps": 1200,
            "fundingSource": "CEX"
        }
        q_params = self._sign(q_params)
        headers = {"X-MBX-APIKEY": self.api_key}

        try:
            q_resp = self.session.post(quote_url, headers=headers, params=q_params, timeout=(3.0, 5.0))
            q_data = q_resp.json()
            if q_resp.status_code != 200:
                code = q_data.get("code")
                msg = q_data.get("msg", str(q_data))
                if code == -9000 or "enough USDT" in msg:
                    return {"success": False, "msg": f"Saldo USDT akun Binance tidak cukup ({msg})"}
                return {"success": False, "msg": f"Gagal quote: {msg}"}

            quote_id = q_data.get("quoteId")
            if not quote_id:
                return {"success": False, "msg": "Quote ID tidak diperoleh dari Binance"}

            # 4. Pasang Order Bundle
            order_url = f"{self.base_url}/sapi/v1/w3w/wallet/prediction/trade/place-order-bundle"
            o_params = {
                "walletAddress": wallet_addr,
                "walletId": wallet_id,
                "quoteId": quote_id,
                "orderType": "MARKET",
                "timeInForce": "FOK",
                "slippageBps": 1200,
                "fundingSource": "CEX"
            }
            o_params = self._sign(o_params)
            o_resp = self.session.post(order_url, headers=headers, params=o_params, timeout=(3.0, 5.0))
            o_data = o_resp.json()
            if o_resp.status_code == 200:
                order_id = o_data.get("orderId", o_data.get("id", "OK"))
                return {"success": True, "data": o_data, "msg": f"Order Real {direction} berhasil dipasang (ID: {order_id})"}
            else:
                return {"success": False, "msg": o_data.get("msg", str(o_data))}

        except requests.exceptions.ConnectTimeout:
            return {"success": False, "msg": "Timeout koneksi saat kirim order (Periksa VPN/Proxy)"}
        except requests.exceptions.ReadTimeout:
            return {"success": False, "msg": "ReadTimeout Binance (Cek histori di aplikasi Binance)"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "msg": "Koneksi internet terputus saat eksekusi order"}
        except Exception as e:
            return {"success": False, "msg": f"Gagal order: {e}"}


class PredictionEngine:
    """
    Engine Pengelola Pasar Prediksi BTC 5 Menit:
    - Menyelaraskan ronde setiap 5 menit jam dinding (00, 05, 10, 15, ..., 55)
    - Mengambil harga Strike awal ronde & Referensi real-time dari Binance
    - Menangani eksekusi Real Trading atau Simulasi secara terpadu
    - Dilengkapi proteksi disconnection & failover data harga
    """
    def __init__(self, client: BinanceClient):
        self.client = client
        self.is_real = not config.SIMULATION_MODE
        self.virtual_balance = config.INITIAL_VIRTUAL_BALANCE
        self.cached_real_balance = 0.0
        self.last_balance_check = 0.0
        self.last_price_timestamp = time.time()
        self.is_online = True
        self.consecutive_errors = 0
        self.current_round: Optional[Dict[str, Any]] = None
        self.active_positions: List[Dict[str, Any]] = []
        self.history: List[Dict[str, Any]] = []
        
        # Inisialisasi harga awal BTC
        try:
            self.live_btc_price = self.client.get_spot_price(config.TARGET_SYMBOL)
            self.last_price_timestamp = time.time()
        except Exception:
            self.live_btc_price = 81000.0
        self.target_strike_price = self.live_btc_price

    def get_balance(self, force_refresh: bool = False) -> float:
        """Mengambil saldo (Riil jika mode LIVE dengan caching 30s & safe retain, Virtual jika mode SIMULASI)"""
        if self.is_real:
            now = time.time()
            if force_refresh or (now - self.last_balance_check > 30):
                try:
                    bal = self.client.get_real_usdt_balance()
                    if bal is not None:
                        self.cached_real_balance = bal
                        self.last_balance_check = now
                except Exception:
                    pass
            return self.cached_real_balance
        return self.virtual_balance

    def update_market_state(self) -> Dict[str, Any]:
        now = time.time()
        round_duration_sec = config.ROUND_MINUTES * 60  # 300 detik

        # Selaraskan expiry dengan kelipatan 5 menit tepat
        current_block = int(now) // round_duration_sec
        expiry_timestamp = (current_block + 1) * round_duration_sec
        round_start_timestamp = current_block * round_duration_sec
        seconds_left = max(0, expiry_timestamp - int(now))

        expiry_dt = datetime.fromtimestamp(expiry_timestamp)
        expiry_str = expiry_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Ambil harga real-time BTC Spot dengan failover & connection tracking
        try:
            self.live_btc_price = self.client.get_spot_price(config.TARGET_SYMBOL)
            self.last_price_timestamp = now
            self.is_online = True
            self.consecutive_errors = 0
        except Exception:
            self.consecutive_errors += 1
            if now - self.last_price_timestamp > 5:
                self.is_online = False

        stale_seconds = int(now - self.last_price_timestamp)

        # Jika masuk ronde 5 menit baru
        if not self.current_round or self.current_round["expiry_timestamp"] != expiry_timestamp:
            if self.current_round:
                self._resolve_round(self.live_btc_price)

            # Kunci harga target strike di awal ronde 5 menit
            self.target_strike_price = self.live_btc_price
            self.current_round = {
                "title": f"{config.TARGET_ASSET} Naik atau Turun dalam {config.ROUND_MINUTES} menit",
                "round_id": f"BTC-{expiry_dt.strftime('%H%M')}",
                "start_timestamp": round_start_timestamp,
                "expiry_timestamp": expiry_timestamp,
                "expiry_str": expiry_str,
                "strike_price": self.target_strike_price,
                "status": "OPEN"
            }

        # Hitung selisih harga spot BTC terhadap target strike
        diff_price = round(self.live_btc_price - self.target_strike_price, 2)
        diff_str = f"+${diff_price:,.2f}" if diff_price >= 0 else f"-${abs(diff_price):,.2f}"

        # Perhitungan peluang dinamis berdasarkan pergerakan BTC
        # Tiap $10 selisih BTC menggeser probabilitas ~1%
        base_naik = 0.50 + ((diff_price / 100.0) * 0.15)
        prob_naik_pct = int(max(10, min(90, round(base_naik * 100))))
        prob_turun_pct = 100 - prob_naik_pct

        # Multiplier Payout 1 USDT (seperti di aplikasi Binance)
        payout_naik_1usdt = round(1.0 / (prob_naik_pct / 100.0) * 0.98, 2) if prob_naik_pct > 0 else 1.0
        payout_turun_1usdt = round(1.0 / (prob_turun_pct / 100.0) * 0.98, 2) if prob_turun_pct > 0 else 1.0

        # Countdown format MM:SS
        mins = seconds_left // 60
        secs = seconds_left % 60
        countdown_str = f"{mins:02d}:{secs:02d}"

        return {
            "title": f"{config.TARGET_ASSET} Naik atau Turun dalam {config.ROUND_MINUTES} menit",
            "expiry_str": expiry_str,
            "strike_price": self.target_strike_price,
            "ref_price": self.live_btc_price,
            "diff_str": diff_str,
            "diff_val": diff_price,
            "seconds_left": seconds_left,
            "countdown_str": countdown_str,
            "prob_naik": prob_naik_pct,
            "prob_turun": prob_turun_pct,
            "payout_naik": payout_naik_1usdt,
            "payout_turun": payout_turun_1usdt,
            "balance_usdt": self.get_balance(),
            "is_online": self.is_online,
            "stale_seconds": stale_seconds
        }

    def place_order(self, direction: str, amount_usdt: float, payout_multiplier: float) -> Dict[str, Any]:
        """Mengeksekusi taruhan (Real API atau Simulasi)"""
        current_bal = self.get_balance()
        
        # Validasi saldo
        if current_bal < amount_usdt:
            mode_name = "riil" if self.is_real else "simulasi"
            return {"success": False, "msg": f"Saldo {mode_name} tidak mencukupi ({current_bal:.2f} USDT < {amount_usdt:.2f} USDT)"}

        # Jika mode REAL TRADING, kirim order ke Binance SAPI
        if self.is_real:
            res = self.client.place_real_prediction_order(direction, amount_usdt)
            if not res.get("success"):
                return res

        # Catat posisi aktif
        if not self.is_real:
            self.virtual_balance = round(self.virtual_balance - amount_usdt, 2)

        pos = {
            "expiry_str": self.current_round["expiry_str"],
            "direction": direction,
            "amount": amount_usdt,
            "payout_multiplier": payout_multiplier,
            "potential_win": round(amount_usdt * payout_multiplier, 2),
            "strike_price": self.target_strike_price,
            "ref_at_entry": self.live_btc_price,
            "timestamp": time.time(),
            "is_real": self.is_real
        }
        self.active_positions.append(pos)
        return {"success": True, "msg": f"Order {direction} terpasang"}

    def _resolve_round(self, final_price: float):
        """Menyelesaikan ronde dan menghitung payout kemenangan"""
        winning_dir = "Naik" if final_price >= self.target_strike_price else "Turun"
        
        remaining = []
        for pos in self.active_positions:
            won = (pos["direction"] == winning_dir)
            payout = pos["potential_win"] if won else 0.0
            profit = round(payout - pos["amount"], 2)

            if not self.is_real:
                self.virtual_balance = round(self.virtual_balance + payout, 2)

            self.history.append({
                "round": pos["expiry_str"][-8:],
                "direction": pos["direction"],
                "won": won,
                "profit": profit,
                "payout": payout,
                "is_real": pos.get("is_real", False)
            })
        self.active_positions = remaining
