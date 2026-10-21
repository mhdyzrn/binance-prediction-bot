import time
import os
import json
import math
import threading
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
        self._active_funding_source: str = "WALLET"
        self.time_offset = 0
        self._sync_server_time()

    def _sync_server_time(self):
        """Menghitung selisih waktu lokal dengan server Binance untuk mencegah error timestamp (-1021)"""
        try:
            resp = self.session.get(f"{self.base_url}/api/v3/time", timeout=(2.0, 3.0))
            if resp.status_code == 200:
                server_time = resp.json().get("serverTime")
                local_time = int(time.time() * 1000)
                self.time_offset = local_time - server_time
        except Exception:
            pass

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Menghasilkan timestamp & signature HMAC-SHA256 resmi Binance"""
        params["timestamp"] = int(time.time() * 1000) - self.time_offset
        params["recvWindow"] = 10000
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

    def get_klines(self, symbol: str = config.TARGET_SYMBOL, interval: str = "1m", limit: int = 20) -> List[Any]:
        """Mengambil data candlestick resmi dari Binance Vision / mirror dengan failover"""
        endpoints = [
            f"{self.market_data_url}/api/v3/klines",
            f"{self.base_url}/api/v3/klines",
            "https://api1.binance.com/api/v3/klines"
        ]
        for ep in endpoints:
            try:
                resp = self.session.get(ep, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=(2.0, 3.5))
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                continue
        return []

    def get_current_5m_strike(self, symbol: str = config.TARGET_SYMBOL) -> Optional[float]:
        """
        Mengambil harga OPEN dari candlestick 5 menit yang sedang berjalan sebagai Strike Price resmi.
        Ini memastikan Strike Price 100% presisi dan sinkron dengan candle Binance,
        bahkan jika bot dinyalakan di tengah-tengah ronde (misal menit ke-2 atau ke-3).
        """
        try:
            klines = self.get_klines(symbol=symbol, interval=f"{config.ROUND_MINUTES}m", limit=1)
            if klines and len(klines) > 0:
                return float(klines[0][1])  # kline index 1 adalah open price
        except Exception:
            pass
        return None

    def calculate_rsi(self, symbol: str = config.TARGET_SYMBOL, period: int = config.RSI_PERIOD) -> Optional[float]:
        """
        Menghitung Indikator RSI (Relative Strength Index) 14 periode pada grafik 1 menit
        secara native dalam Python (tanpa membutuhkan library eksternal/berat di Termux).
        """
        try:
            klines = self.get_klines(symbol=symbol, interval="1m", limit=period + 10)
            if not klines or len(klines) < period + 1:
                return None
            closes = [float(k[4]) for k in klines]
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

            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period

            if avg_loss == 0:
                return 100.0
            rs = avg_gain / avg_loss
            return round(100.0 - (100.0 / (1.0 + rs)), 2)
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

    def get_prediction_balance_details(self) -> tuple[float, float, List[str]]:
        """
        Mengambil detail saldo Web3 Prediction dan daftar token kemenangan yang siap di-klaim:
        Mengembalikan (wallet_balance, claimable_balance, claimable_token_ids)
        """
        wallet, _ = self.get_prediction_wallet()
        if not wallet or not wallet.get("walletAddress"):
            return 0.0, 0.0, []

        headers = {"X-MBX-APIKEY": self.api_key}
        bal = 0.0
        claimable = 0.0
        claimable_tokens = []

        # 1. Ambil wallet balance & summary dari position/list
        url = f"{self.base_url}/sapi/v1/w3w/wallet/prediction/position/list"
        params = self._sign({"walletAddress": wallet["walletAddress"]})
        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=(3.0, 5.0))
            if resp.status_code == 200:
                data = resp.json()
                summary = data.get("summary", {})
                bal = float(summary.get("walletBalance", 0.0))
                claimable = float(summary.get("totalClaimableAmount", 0.0))
        except Exception:
            pass

        # 2. Ambil token ID kemenangan dari position/filter
        filter_url = f"{self.base_url}/sapi/v1/w3w/wallet/prediction/position/filter"
        f_params = self._sign({"walletAddress": wallet["walletAddress"]})
        try:
            f_resp = self.session.get(filter_url, headers=headers, params=f_params, timeout=(3.0, 5.0))
            if f_resp.status_code == 200:
                f_data = f_resp.json()
                for p in f_data.get("positions", []):
                    if p.get("canClaim") and p.get("tokenId"):
                        claimable_tokens.append(p["tokenId"])
        except Exception:
            pass

        return bal, claimable, claimable_tokens

    def claim_prediction_winnings(self, token_ids: Optional[List[str]] = None) -> tuple[bool, str]:
        """
        Klaim / redeem hasil kemenangan prediksi Web3 secara otomatis ke saldo wallet.
        Menggunakan endpoint resmi POST /sapi/v1/w3w/wallet/prediction/batch-redeem via signed query params.
        """
        wallet, err = self.get_prediction_wallet()
        if not wallet or not wallet.get("walletAddress") or not wallet.get("walletId"):
            return False, err or "Prediction wallet tidak ditemukan"

        if not token_ids:
            _, _, token_ids = self.get_prediction_balance_details()

        if not token_ids:
            return False, "Tidak ada kemenangan tertunda yang perlu di-klaim"

        url = f"{self.base_url}/sapi/v1/w3w/wallet/prediction/batch-redeem"
        token_str = token_ids[0] if isinstance(token_ids, list) and len(token_ids) == 1 else ",".join(token_ids)
        params = self._sign({
            "walletAddress": wallet["walletAddress"],
            "walletId": wallet["walletId"],
            "tokenIds": token_str,
            "chainId": "56"
        })
        headers = {"X-MBX-APIKEY": self.api_key}

        try:
            resp = self.session.post(url, headers=headers, params=params, timeout=(4.0, 8.0))
            if resp.status_code == 200:
                return True, f"Berhasil klaim {len(token_ids)} hadiah kemenangan on-chain"
            data = resp.json()
            return False, data.get("msg", resp.text)
        except Exception as e:
            return False, f"Gagal klaim hadiah: {e}"

    def get_spot_usdt_balance(self) -> float:
        """Mengambil saldo USDT free di Spot Wallet Binance"""
        if not self.api_key or not self.api_secret:
            return 0.0
        url = f"{self.base_url}/api/v3/account"
        params = self._sign({})
        headers = {"X-MBX-APIKEY": self.api_key}
        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=(3.0, 5.0))
            if resp.status_code == 200:
                for b in resp.json().get("balances", []):
                    if b.get("asset") == "USDT":
                        return float(b.get("free", 0.0))
        except Exception:
            pass
        return 0.0

    def get_real_usdt_balance(self) -> Optional[float]:
        """
        Mengambil saldo USDT riil akun Binance:
        Mendukung pengecekan saldo Web3 Prediction Wallet dan Spot Wallet.
        Mengembalikan None jika jaringan terputus total agar tidak menimpa saldo sebelumnya.
        """
        if not self.api_key or not self.api_secret:
            return 0.0

        try:
            pred_bal, claimable, claimable_tokens = self.get_prediction_balance_details()
            # Coba auto-claim hadiah jika ada
            if claimable_tokens:
                self.claim_prediction_winnings(claimable_tokens)
                pred_bal, _, _ = self.get_prediction_balance_details()

            spot_bal = self.get_spot_usdt_balance()

            cfg_source = getattr(config, "FUNDING_SOURCE", "AUTO").upper()
            if cfg_source == "WALLET":
                self._active_funding_source = "WALLET"
                return pred_bal
            elif cfg_source == "CEX":
                self._active_funding_source = "CEX"
                return spot_bal
            else:  # AUTO
                if pred_bal > 0:
                    self._active_funding_source = "WALLET"
                    return pred_bal
                elif spot_bal > 0:
                    self._active_funding_source = "CEX"
                    return spot_bal
                else:
                    self._active_funding_source = "WALLET"
                    return 0.0
        except Exception:
            return None

    def test_account_connection(self) -> tuple[bool, str, float]:
        """
        Menguji koneksi ke Binance API dan mendeteksi saldo USDT riil:
        Mengecek Web3 Prediction Wallet dan Spot Wallet secara komprehensif.
        Mengembalikan (status_sukses, pesan, saldo_usdt_aktif).
        """
        if not self.api_key or not self.api_secret:
            return False, "API Key / Secret belum diisi di file .env", 0.0

        # 1. Cek Web3 Prediction Wallet
        pred_wallet, w_err = self.get_prediction_wallet()
        pred_bal = 0.0
        claimable = 0.0
        pred_connected = False
        if pred_wallet and pred_wallet.get("walletAddress"):
            pred_connected = True
            pred_bal, claimable, _ = self.get_prediction_balance_details()

        # 2. Cek Spot Account
        spot_bal = 0.0
        spot_connected = False
        spot_err = None
        try:
            url = f"{self.base_url}/api/v3/account"
            params = self._sign({})
            headers = {"X-MBX-APIKEY": self.api_key}
            resp = self.session.get(url, headers=headers, params=params, timeout=(3.0, 5.0))
            if resp.status_code == 200:
                spot_connected = True
                for b in resp.json().get("balances", []):
                    if b.get("asset") == "USDT":
                        spot_bal = float(b.get("free", 0.0))
                        break
            else:
                spot_err = resp.json().get("msg", resp.text) if resp.headers.get("content-type") == "application/json" else resp.text[:60]
        except Exception as e:
            spot_err = str(e)

        # Evaluasi hasil koneksi
        if not pred_connected and not spot_connected:
            err_msg = w_err or spot_err or "Gagal terhubung ke server Binance"
            return False, f"Respon Binance: {err_msg}", 0.0

        # Tentukan active balance & active funding source
        cfg_source = getattr(config, "FUNDING_SOURCE", "AUTO").upper()
        if cfg_source == "WALLET":
            self._active_funding_source = "WALLET"
            active_bal = pred_bal
        elif cfg_source == "CEX":
            self._active_funding_source = "CEX"
            active_bal = spot_bal
        else:  # AUTO
            if pred_bal > 0:
                self._active_funding_source = "WALLET"
                active_bal = pred_bal
            elif spot_bal > 0:
                self._active_funding_source = "CEX"
                active_bal = spot_bal
            else:
                self._active_funding_source = "WALLET"
                active_bal = 0.0

        msg = f"Koneksi berhasil! (Prediction: {pred_bal:.2f} USDT, Spot: {spot_bal:.2f} USDT)"
        return True, msg, active_bal

    def check_sas_authorization(self) -> tuple[bool, str]:
        """Memeriksa apakah izin Secure Auto-Signing (SAS) sudah aktif di aplikasi Binance"""
        wallet, err = self.get_prediction_wallet()
        if not wallet or not wallet.get("walletAddress") or not wallet.get("walletId"):
            return False, err or "Wallet Web3 tidak ditemukan"

        url = f"{self.base_url}/sapi/v1/w3w/wallet/prediction/trade/place-order-bundle"
        params = self._sign({
            "walletAddress": wallet["walletAddress"],
            "walletId": wallet["walletId"],
            "quoteId": "sas_probe_check",
            "orderType": "MARKET",
            "timeInForce": "FOK",
            "slippageBps": 2000,
            "fundingSource": "MPC",
            "accountType": "SPOT"
        })
        headers = {"X-MBX-APIKEY": self.api_key}
        try:
            resp = self.session.post(url, headers=headers, params=params, timeout=(3.0, 5.0))
            data = resp.json()
            code = data.get("code")
            msg = data.get("msg", "")
            if code == -31003 or "SAS authorization" in msg:
                return False, "SAS belum diaktifkan di aplikasi Binance"
            # Jika lolos dari error -31003 (misal error quoteId invalid), berarti SAS sudah aktif
            return True, "SAS aktif"
        except Exception as e:
            return False, str(e)

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
                    t_lower = title.lower()
                    if "btc" in t_lower and "5m" in t_lower:
                        return topic, None
                return None, "Pasar prediksi BTC 5m sedang tidak aktif di server Binance"
            return None, f"Gagal memuat pasar ({resp.status_code})"
        except requests.exceptions.Timeout:
            return None, "Koneksi timeout saat memuat pasar prediksi"
        except requests.exceptions.ConnectionError:
            return None, "Koneksi terputus saat memuat pasar prediksi"
        except Exception as e:
            return None, f"Error pasar: {e}"

    def get_prediction_strike(self) -> Optional[float]:
        """
        Mengambil harga Strike resmi (variantData.startPrice) dari Binance Web3 Prediction SAPI.
        Menggunakan oracle Chainlink resmi Binance, bukan estimasi candlestick spot.
        """
        try:
            topic, _ = self.get_active_btc_prediction_market()
            if topic and topic.get("variantData"):
                start_p = topic["variantData"].get("startPrice")
                if start_p:
                    return float(start_p)
        except Exception:
            pass
        return None

    def get_pending_claim_positions(self) -> List[Dict[str, Any]]:
        """Mengambil posisi aktif / pending claim resmi dari Binance Web3 Prediction SAPI"""
        wallet, _ = self.get_prediction_wallet()
        if not wallet or not wallet.get("walletAddress"):
            return []

        url = f"{self.base_url}/sapi/v1/w3w/wallet/prediction/position/filter"
        params = self._sign({"walletAddress": wallet["walletAddress"]})
        headers = {"X-MBX-APIKEY": self.api_key}
        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=(3.0, 5.0))
            if resp.status_code == 200:
                return resp.json().get("positions", [])
        except Exception:
            pass
        return []

    def get_real_settled_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Mengambil riwayat posisi yang sudah selesai (settled) resmi dari Binance Web3 Prediction SAPI:
        GET /sapi/v1/w3w/wallet/prediction/position/settled-history
        """
        wallet, _ = self.get_prediction_wallet()
        if not wallet or not wallet.get("walletAddress"):
            return []

        url = f"{self.base_url}/sapi/v1/w3w/wallet/prediction/position/settled-history"
        params = self._sign({"walletAddress": wallet["walletAddress"], "limit": limit})
        headers = {"X-MBX-APIKEY": self.api_key}
        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=(4.0, 8.0))
            if resp.status_code == 200:
                data = resp.json()
                return data.get("positions", [])
        except Exception:
            pass
        return []

    def get_portfolio_pnl(self) -> Optional[Dict[str, Any]]:
        """Mengambil ringkasan PnL portofolio Web3 Prediction dari Binance SAPI"""
        wallet, _ = self.get_prediction_wallet()
        if not wallet or not wallet.get("walletAddress"):
            return None

        url = f"{self.base_url}/sapi/v1/w3w/wallet/prediction/pnl/portfolio"
        params = self._sign({"walletAddress": wallet["walletAddress"]})
        headers = {"X-MBX-APIKEY": self.api_key}
        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=(3.0, 5.0))
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

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

        # Tentukan sumber dana (MPC atau CEX)
        # Sesuai dokumentasi resmi Binance SAPI place-order-bundle:
        # fundingSource wajib bernilai 'MPC' (Web3 Wallet) atau 'CEX' (Spot)
        cfg_source = getattr(config, "FUNDING_SOURCE", "AUTO").upper()
        if cfg_source in ["MPC", "WALLET"]:
            funding_source = "MPC"
        elif cfg_source == "CEX":
            funding_source = "CEX"
        else:
            # Mode AUTO: utamakan Web3 Prediction Wallet (MPC) jika saldo mencukupi
            pred_bal, _, _ = self.get_prediction_balance_details()
            if pred_bal >= amount_usdt:
                funding_source = "MPC"
            else:
                spot_bal = self.get_spot_usdt_balance()
                if spot_bal >= amount_usdt:
                    funding_source = "CEX"
                else:
                    funding_source = "MPC"
        self._active_funding_source = "WALLET" if funding_source == "MPC" else "CEX"

        # 3. Dapatkan Quote
        quote_url = f"{self.base_url}/sapi/v1/w3w/wallet/prediction/trade/get-quote"
        amount_wei = str(int(amount_usdt * 1e18))
        slippage = getattr(config, "SLIPPAGE_BPS", 2000)
        q_params = {
            "walletAddress": wallet_addr,
            "tokenId": token_id,
            "side": "BUY",
            "amountIn": amount_wei,
            "orderType": "MARKET",
            "slippageBps": slippage,
            "fundingSource": funding_source
        }
        q_params = self._sign(q_params)
        headers = {"X-MBX-APIKEY": self.api_key}

        try:
            q_resp = self.session.post(quote_url, headers=headers, params=q_params, timeout=(3.0, 5.0))
            q_data = q_resp.json()
            if q_resp.status_code != 200:
                code = q_data.get("code")
                msg = q_data.get("msg", str(q_data))
                msg_lower = msg.lower()
                if "enough usdt" in msg_lower or "insufficient balance" in msg_lower:
                    return {"success": False, "msg": f"Saldo USDT tidak cukup ({msg})"}
                elif "liquidity" in msg_lower:
                    return {"success": False, "msg": f"Likuiditas tipis / ronde hampir berakhir ({msg})"}
                elif "too small" in msg_lower:
                    return {"success": False, "msg": f"Nominal taruhan di bawah batas minimal ({msg})"}
                return {"success": False, "msg": f"Gagal quote: {msg}"}

            quote_id = q_data.get("quoteId")
            if not quote_id:
                return {"success": False, "msg": "Quote ID tidak diperoleh dari Binance"}

            actual_shares = float(q_data.get("amountOut", 0)) / 1e18
            average_price = float(q_data.get("averagePrice", 0))

            # 4. Pasang Order Bundle
            order_url = f"{self.base_url}/sapi/v1/w3w/wallet/prediction/trade/place-order-bundle"
            o_params = {
                "walletAddress": wallet_addr,
                "walletId": wallet_id,
                "quoteId": quote_id,
                "orderType": "MARKET",
                "timeInForce": "FOK",
                "slippageBps": slippage,
                "fundingSource": funding_source,
                "accountType": "SPOT"
            }
            o_params = self._sign(o_params)
            o_resp = self.session.post(order_url, headers=headers, params=o_params, timeout=(3.0, 5.0))
            o_data = o_resp.json()
            if o_resp.status_code == 200:
                order_id = o_data.get("orderId", o_data.get("id", "OK"))
                return {
                    "success": True,
                    "data": o_data,
                    "actual_payout": round(actual_shares, 2) if actual_shares > 0 else None,
                    "average_price": average_price,
                    "msg": f"Order Real {direction} berhasil dipasang (ID: {order_id})"
                }
            else:
                code = o_data.get("code")
                msg = o_data.get("msg", str(o_data))
                if code == -31003 or "SAS authorization" in msg:
                    return {"success": False, "msg": "Wajib aktifkan Secure Auto-Signing (SAS) di aplikasi Binance: [Dompet] > [Prediction] > [Settings]"}
                return {"success": False, "msg": msg}

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
    - Mengambil harga Strike resmi (Oracle Chainlink di Mode Real, Candlestick Open di Simulasi)
    - Verifikasi resolusi resmi on-chain via GET /sapi/v1/w3w/wallet/prediction/position/settled-history
    - Menjamin Net PnL, Win/Loss, dan Payout 100% identik dengan aplikasi Binance
    - Dilengkapi proteksi disconnection & failover data harga
    """
    def __init__(self, client: BinanceClient):
        self.client = client
        self.is_real = not config.SIMULATION_MODE
        self.cached_real_balance = 0.0
        self.last_balance_check = 0.0
        self.last_price_timestamp = time.time()
        self.is_online = True
        self.consecutive_errors = 0
        self.current_round: Optional[Dict[str, Any]] = None
        self.active_positions: List[Dict[str, Any]] = []
        self.pending_settlement: List[Dict[str, Any]] = []
        self.last_settlement_check = 0.0
        self._strike_is_fallback = False
        
        # State RSI & Proteksi Cooldown
        self.cached_rsi: Optional[float] = None
        self.last_rsi_update = 0.0
        self.consecutive_losses = 0
        self.cooldown_rounds_left = 0
        self.last_cooldown_loss_id = None

        # Riwayat transaksi tersimpan permanen di file terpisah (Real vs Simulasi)
        self.history_file = config.REAL_HISTORY_FILE if self.is_real else config.SIM_HISTORY_FILE
        self.history: List[Dict[str, Any]] = self._load_history()

        # Evaluasi kekalahan berturut-turut dari riwayat
        loss_cnt = 0
        for h in reversed(self.history):
            if not h.get("won"):
                loss_cnt += 1
            else:
                break
        self.consecutive_losses = loss_cnt
        latest_trade = self.history[-1] if self.history else None
        latest_end_ts = latest_trade.get("end_timestamp", 0) if latest_trade else 0
        cooldown_window_sec = config.COOLDOWN_ROUNDS * config.ROUND_MINUTES * 60
        is_recent = (time.time() - latest_end_ts) <= cooldown_window_sec if latest_end_ts else False

        if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSS and is_recent:
            self.cooldown_rounds_left = config.COOLDOWN_ROUNDS
            self.last_cooldown_loss_id = latest_trade.get("position_id")
        else:
            self.cooldown_rounds_left = 0
            if latest_trade:
                self.last_cooldown_loss_id = latest_trade.get("position_id")
            if not is_recent:
                self.consecutive_losses = 0

        # Saldo simulasi tersimpan permanen agar tidak ter-reset jika tidak habis
        self.sim_balance_file = config.SIM_BALANCE_FILE
        self.virtual_balance = self._load_virtual_balance()
        
        # Inisialisasi harga awal BTC & Strike resmi 5M
        try:
            self.live_btc_price = self.client.get_spot_price(config.TARGET_SYMBOL)
            self.last_price_timestamp = time.time()
        except Exception:
            self.live_btc_price = 81000.0

        official_strike = None
        if self.is_real:
            official_strike = self.client.get_prediction_strike()
        if official_strike is None:
            official_strike = self.client.get_current_5m_strike(config.TARGET_SYMBOL)
            self._strike_is_fallback = (self.is_real and official_strike is not None)
        else:
            self._strike_is_fallback = False

        self.target_strike_price = official_strike if official_strike is not None else self.live_btc_price
        if self.is_real:
            self.sync_active_positions()

        # Worker thread latar belakang untuk update harga & status tanpa memblokir hitung mundur detik
        self._bg_running = True
        self._bg_thread = threading.Thread(target=self._bg_worker, daemon=True)
        self._bg_thread.start()

    def _bg_worker(self):
        """Worker thread latar belakang untuk menjaga data pasar dan koneksi real-time tanpa latensi UI"""
        while getattr(self, "_bg_running", True):
            now = time.time()
            # 1. Update harga live spot BTC
            try:
                p = self.client.get_spot_price(config.TARGET_SYMBOL)
                self.live_btc_price = p
                self.last_price_timestamp = now
                self.is_online = True
                self.consecutive_errors = 0
            except Exception:
                self.consecutive_errors += 1
                if now - self.last_price_timestamp > 5:
                    self.is_online = False

            # 2. Update RSI secara berkala (tiap 3 detik)
            if now - self.last_rsi_update >= 3.0:
                try:
                    val_rsi = self.client.calculate_rsi(config.TARGET_SYMBOL, config.RSI_PERIOD)
                    if val_rsi is not None:
                        self.cached_rsi = val_rsi
                    self.last_rsi_update = now
                except Exception:
                    pass

            # 3. Periksa status pending settlement jika ada posisi menunggu oracle
            if self.is_real and self.pending_settlement and (now - self.last_settlement_check >= 3.0):
                try:
                    self._check_pending_settlements()
                    self.last_settlement_check = now
                except Exception:
                    pass

            # 4. Sinkronkan harga Strike & kuotasi Buku Order Web3 resmi Binance
            if (now - getattr(self, "_last_market_poll", 0)) >= 2.0:
                try:
                    topic, _ = self.client.get_active_btc_prediction_market()
                    if topic:
                        # Update strike resmi jika sebelumnya fallback
                        if self._strike_is_fallback and topic.get("variantData"):
                            real_strike = topic["variantData"].get("startPrice")
                            if real_strike:
                                self.target_strike_price = float(real_strike)
                                self._strike_is_fallback = False
                                if self.current_round:
                                    self.current_round["strike_price"] = self.target_strike_price

                        # Ambil harga tiket & probabilitas order book resmi Binance Web3
                        if topic.get("markets"):
                            for out in topic["markets"][0].get("outcomes", []):
                                name = out.get("name")
                                p_val = float(out.get("price", 0))
                                ch_val = float(out.get("chance", p_val))
                                if name == "Up" and p_val > 0:
                                    self.real_up_price = p_val
                                    self.real_up_chance = ch_val
                                elif name == "Down" and p_val > 0:
                                    self.real_down_price = p_val
                                    self.real_down_chance = ch_val
                    self._last_market_poll = now
                except Exception:
                    pass

            time.sleep(0.5)

    def sync_active_positions(self):
        """
        Mendeteksi posisi aktif atau pending claim yang sedang berjalan di Binance saat bot dimulai.
        Mencegah double betting jika bot di-restart di tengah ronde.
        """
        if not self.is_real:
            return

        try:
            positions = self.client.get_pending_claim_positions()
            if not positions:
                return

            now = time.time()
            existing_pos_ids = {h.get("position_id") for h in self.history if h.get("position_id")}
            for p in positions:
                pos_id = p.get("positionId")
                if pos_id and pos_id in existing_pos_ids:
                    continue

                topic_title = p.get("marketTopicTitle", "")
                if topic_title and "BTC" not in topic_title.upper() and "BITCOIN" not in topic_title.upper():
                    continue

                end_ts = p.get("endDate", 0) / 1000.0
                status = str(p.get("positionStatus", "")).upper()
                direction = "Naik" if p.get("outcomeName") == "Up" else "Turun"
                amount = round(float(p.get("totalCost", 1.0)), 2)
                potential_win = round(float(p.get("shares", 1.0)), 2)
                expiry_dt = datetime.fromtimestamp(end_ts)
                expiry_str = expiry_dt.strftime("%Y-%m-%d %H:%M:%S")

                # Jika ronde masih aktif: masukkan ke active_positions
                if end_ts > now and status in ["REGISTERED", "ACTIVE"]:
                    if not any(a.get("order_data", {}).get("positionId") == pos_id for a in self.active_positions):
                        self.active_positions.append({
                            "expiry_str": expiry_str,
                            "expiry_timestamp": int(end_ts),
                            "direction": direction,
                            "amount": amount,
                            "payout_multiplier": (potential_win / amount) if amount > 0 else 1.0,
                            "potential_win": potential_win,
                            "strike_price": self.target_strike_price,
                            "ref_at_entry": self.live_btc_price,
                            "timestamp": time.time(),
                            "is_real": True,
                            "order_data": p
                        })
                # Jika ronde sudah expired tapi belum settled: masukkan ke pending_settlement
                elif end_ts <= now:
                    if not any(ps.get("order_data", {}).get("positionId") == pos_id for ps in self.pending_settlement):
                        self.pending_settlement.append({
                            "expiry_str": expiry_str,
                            "expiry_timestamp": int(end_ts),
                            "direction": direction,
                            "amount": amount,
                            "payout_multiplier": (potential_win / amount) if amount > 0 else 1.0,
                            "potential_win": potential_win,
                            "strike_price": self.target_strike_price,
                            "ref_at_entry": self.live_btc_price,
                            "resolution_submitted_at": time.time(),
                            "timestamp": time.time(),
                            "is_real": True,
                            "order_data": p
                        })
        except Exception:
            pass

    def _load_history(self) -> List[Dict[str, Any]]:
        """Memuat riwayat transaksi dari disk. Pada mode Real, sinkronkan langsung dengan Binance SAPI"""
        if self.is_real:
            synced = self.sync_real_history(save=True)
            if synced:
                return synced

        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [d for d in data if d.get("is_real", False) == self.is_real]
            except Exception:
                pass
        return []

    def sync_real_history(self, save: bool = True) -> List[Dict[str, Any]]:
        """
        Mensinkronisasikan riwayat transaksi riil langsung dari Binance SAPI Web3 Prediction.
        Menjamin status Menang/Kalah (Win/Loss) dan Net PnL 100% identik dengan aplikasi Binance.
        """
        if not self.is_real:
            return self.history

        try:
            positions = self.client.get_real_settled_history(limit=50)
            if not positions:
                return self.history

            synced: List[Dict[str, Any]] = []
            for p in positions:
                topic_title = p.get("marketTopicTitle", "")
                if topic_title and "BTC" not in topic_title.upper() and "BITCOIN" not in topic_title.upper():
                    continue

                end_ts = p.get("endDate", 0) / 1000.0
                round_str = datetime.fromtimestamp(end_ts).strftime("%H:%M:%S")
                dir_str = "Naik" if p.get("outcomeName") == "Up" else "Turun"
                won = bool(p.get("isWinner", False))
                profit = round(float(p.get("realizedPnl", 0.0)), 2)
                amount = round(float(p.get("totalCost", 0.0)), 2)
                if profit == 0.0 and not won and amount > 0:
                    profit = -amount
                payout = round(amount + profit, 2) if won else 0.0

                synced.append({
                    "round": round_str,
                    "direction": dir_str,
                    "won": won,
                    "profit": profit,
                    "payout": payout,
                    "amount": amount,
                    "strike": None,
                    "final_price": p.get("finalOutcome"),
                    "is_real": True,
                    "position_id": p.get("positionId"),
                    "market_title": topic_title,
                    "end_timestamp": end_ts
                })

            synced.reverse()  # Urutan kronologis (terlama ke terbaru)
            self.history = synced

            # Evaluasi kekalahan berturut-turut untuk proteksi cooldown
            loss_cnt = 0
            for h in reversed(synced):
                if not h.get("won"):
                    loss_cnt += 1
                else:
                    break
            self.consecutive_losses = loss_cnt
            latest_trade = synced[-1] if synced else None
            latest_id = latest_trade.get("position_id") if latest_trade else None
            latest_end_ts = latest_trade.get("end_timestamp", 0) if latest_trade else 0
            cooldown_window_sec = config.COOLDOWN_ROUNDS * config.ROUND_MINUTES * 60
            is_recent = (time.time() - latest_end_ts) <= cooldown_window_sec if latest_end_ts else False

            # Cooldown hanya aktif jika:
            # 1. Kekalahan beruntun >= MAX_CONSECUTIVE_LOSS
            # 2. Kekalahan terjadi baru-baru ini (dalam rentang waktu jeda ronde)
            # 3. ID kekalahan ini belum pernah memicu cooldown sebelumnya
            if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSS and is_recent:
                if self.last_cooldown_loss_id != latest_id:
                    self.cooldown_rounds_left = config.COOLDOWN_ROUNDS
                    self.last_cooldown_loss_id = latest_id
            elif not is_recent:
                self.cooldown_rounds_left = 0
                if latest_id:
                    self.last_cooldown_loss_id = latest_id
                self.consecutive_losses = 0

            if save:
                self._save_history()
            return synced
        except Exception:
            return self.history

    def _save_history(self):
        """Menyimpan riwayat transaksi ke disk"""
        try:
            with open(self.history_file, "w") as f:
                json.dump(self.history[-200:], f, indent=2)
        except Exception:
            pass

    def _load_virtual_balance(self) -> float:
        """
        Memuat saldo simulasi tersimpan dari disk agar tidak ter-reset jika saldo belum habis.
        Jika saldo tersisa < taruhan minimal (saldo habis), barulah di-reset kembali ke saldo awal ($10).
        """
        if os.path.exists(self.sim_balance_file):
            try:
                with open(self.sim_balance_file, "r") as f:
                    data = json.load(f)
                    bal = float(data.get("virtual_balance", config.INITIAL_VIRTUAL_BALANCE))
                    # Jika saldo masih cukup untuk bertaruh (belum habis), jangan reset!
                    if bal >= config.BET_AMOUNT_USDT:
                        return round(bal, 2)
            except Exception:
                pass
        return config.INITIAL_VIRTUAL_BALANCE

    def _save_virtual_balance(self):
        """Menyimpan saldo simulasi ke disk"""
        try:
            with open(self.sim_balance_file, "w") as f:
                json.dump({"virtual_balance": round(self.virtual_balance, 2), "updated_at": time.time()}, f, indent=2)
        except Exception:
            pass

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

        # Status koneksi diukur dari waktu harga terakhir diperbarui oleh worker thread
        if now - self.last_price_timestamp > 5:
            self.is_online = False
        stale_seconds = int(now - self.last_price_timestamp)

        # Jika masuk ronde 5 menit baru
        if not self.current_round or self.current_round["expiry_timestamp"] != expiry_timestamp:
            if self.current_round:
                self._resolve_round(self.live_btc_price)
                if self.cooldown_rounds_left > 0:
                    self.cooldown_rounds_left -= 1
                    if self.cooldown_rounds_left == 0:
                        self.consecutive_losses = 0
            if self.is_real:
                try:
                    self.sync_real_history(save=True)
                except Exception:
                    pass

            # Ambil harga strike resmi (Chainlink Oracle resmi di Mode Real, Candlestick Open di Simulasi)
            official_strike = None
            if self.is_real:
                official_strike = self.client.get_prediction_strike()
            if official_strike is None:
                official_strike = self.client.get_current_5m_strike(config.TARGET_SYMBOL)
                self._strike_is_fallback = (self.is_real and official_strike is not None)
            else:
                self._strike_is_fallback = False

            self.target_strike_price = official_strike if official_strike is not None else self.live_btc_price

            market_name = f"{config.TARGET_ASSET} Naik atau Turun dalam {config.ROUND_MINUTES} Menit?"
            self.current_round = {
                "title": market_name,
                "market_name": market_name,
                "round_id": f"{config.TARGET_ASSET}-{expiry_dt.strftime('%H%M')}",
                "start_timestamp": round_start_timestamp,
                "expiry_timestamp": expiry_timestamp,
                "expiry_str": expiry_str,
                "strike_price": self.target_strike_price,
                "status": "OPEN"
            }

        # Cek pembaruan strike jika sebelumnya fallback dan topik Web3 baru sudah terbuka
        if self.is_real and self._strike_is_fallback and (seconds_left > config.SNIPER_TRIGGER_SECONDS):
            real_strike = self.client.get_prediction_strike()
            if real_strike is not None:
                self.target_strike_price = real_strike
                self._strike_is_fallback = False
                if self.current_round:
                    self.current_round["strike_price"] = real_strike

        # Hitung selisih harga spot BTC terhadap target strike
        diff_price = round(self.live_btc_price - self.target_strike_price, 2)
        diff_str = f"+${diff_price:,.2f}" if diff_price >= 0 else f"-${abs(diff_price):,.2f}"

        # Probabilitas & Payout rasio diambil langsung dari Buku Order Resmi Binance Web3 jika tersedia
        real_up = getattr(self, "real_up_price", None)
        real_down = getattr(self, "real_down_price", None)
        if self.is_real and real_up and real_down and real_up > 0 and real_down > 0:
            up_chance = getattr(self, "real_up_chance", real_up)
            down_chance = getattr(self, "real_down_chance", real_down)
            prob_naik_pct = int(round(up_chance * 100))
            prob_turun_pct = 100 - prob_naik_pct
            # Payout rasio per 1 USDT setelah memperhitungkan fee AMM Binance (2%)
            payout_naik_mult = round((1.0 / real_up) * 0.98, 2)
            payout_turun_mult = round((1.0 / real_down) * 0.98, 2)
        else:
            # Fallback ke formula volatilitas delta jika data order book Web3 belum termuat / Mode Simulasi
            t_ratio = max(10, min(300, seconds_left)) / 300.0
            time_factor = math.sqrt(t_ratio)
            sigma = 80.0 * time_factor
            z = diff_price / sigma
            z = max(-15.0, min(15.0, z))
            p_naik_raw = 1.0 / (1.0 + math.exp(-z))
            prob_naik_pct = int(round(p_naik_raw * 99))
            prob_naik_pct = max(1, min(98, prob_naik_pct))
            prob_turun_pct = 99 - prob_naik_pct
            payout_naik_mult = round(1.0 / (prob_naik_pct / 100.0), 2) if prob_naik_pct > 0 else 1.0
            payout_turun_mult = round(1.0 / (prob_turun_pct / 100.0), 2) if prob_turun_pct > 0 else 1.0

        current_bal = self.get_balance()
        bet_amount, compound_tier = config.calculate_compound_bet(current_bal)

        # Estimasi total perolehan USDT jika menang sesuai nominal taruhan (bet_amount) saat ini
        win_naik_usdt = round(bet_amount * payout_naik_mult, 2)
        win_turun_usdt = round(bet_amount * payout_turun_mult, 2)

        # Countdown format MM:SS
        mins = seconds_left // 60
        secs = seconds_left % 60
        countdown_str = f"{mins:02d}:{secs:02d}"

        # Statistik akumulatif sesi (difilter ketat sesuai mode aktif: REAL atau SIMULASI)
        active_hist = [h for h in self.history if h.get("is_real", False) == self.is_real]
        total_trades = len(active_hist)
        wins = sum(1 for h in active_hist if h.get("won"))
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        net_pnl = sum(h.get("profit", 0.0) for h in active_hist)

        market_name = f"{config.TARGET_ASSET} Naik atau Turun dalam {config.ROUND_MINUTES} Menit?"
        return {
            "title": market_name,
            "market_name": market_name,
            "expiry_str": expiry_str,
            "strike_price": self.target_strike_price,
            "ref_price": self.live_btc_price,
            "diff_str": diff_str,
            "diff_val": diff_price,
            "seconds_left": seconds_left,
            "countdown_str": countdown_str,
            "prob_naik": prob_naik_pct,
            "prob_turun": prob_turun_pct,
            "payout_naik": payout_naik_mult,
            "payout_turun": payout_turun_mult,
            "win_naik_usdt": win_naik_usdt,
            "win_turun_usdt": win_turun_usdt,
            "balance_usdt": current_bal,
            "funding_source": getattr(self.client, "_active_funding_source", "WALLET"),
            "bet_amount": bet_amount,
            "compound_tier": compound_tier,

            "is_online": self.is_online,
            "stale_seconds": stale_seconds,
            "rsi": self.cached_rsi,
            "in_cooldown": (self.cooldown_rounds_left > 0),
            "cooldown_rounds_left": self.cooldown_rounds_left,
            "consecutive_losses": self.consecutive_losses,
            "has_pending_settlement": (len(self.pending_settlement) > 0),
            "pending_settlement_count": len(self.pending_settlement),
            "total_trades": total_trades,
            "wins": wins,
            "win_rate": win_rate,
            "net_pnl": round(net_pnl, 2)
        }

    def place_order(self, direction: str, amount_usdt: float, payout_multiplier: float) -> Dict[str, Any]:
        """Mengeksekusi taruhan (Real API atau Simulasi)"""
        # Cegah double order jika sudah ada posisi aktif di ronde ini
        if self.active_positions:
            return {"success": False, "msg": "Sudah ada posisi aktif di ronde ini"}

        current_bal = self.get_balance()
        
        # Validasi saldo
        if current_bal < amount_usdt:
            mode_name = "riil" if self.is_real else "simulasi"
            return {"success": False, "msg": f"Saldo {mode_name} tidak mencukupi ({current_bal:.2f} USDT < {amount_usdt:.2f} USDT)"}

        # Jika mode REAL TRADING, kirim order ke Binance SAPI
        order_data = None
        potential_win = round(amount_usdt * payout_multiplier, 2)
        if self.is_real:
            res = self.client.place_real_prediction_order(direction, amount_usdt)
            if not res.get("success"):
                return res
            order_data = res.get("data")
            # Ambil nilai payout riil resmi dari get-quote Binance SAPI
            actual_payout = res.get("actual_payout")
            if actual_payout and actual_payout > 0:
                potential_win = round(actual_payout, 2)
                payout_multiplier = round(actual_payout / amount_usdt, 2)

        # Catat posisi aktif
        if not self.is_real:
            self.virtual_balance = round(self.virtual_balance - amount_usdt, 2)
            self._save_virtual_balance()

        expiry_id = self.current_round["expiry_str"] if self.current_round else "SIM-ROUND"
        expiry_ts = self.current_round["expiry_timestamp"] if self.current_round else (int(time.time() // 300 + 1) * 300)
        pos = {
            "expiry_str": expiry_id,
            "expiry_timestamp": expiry_ts,
            "direction": direction,
            "amount": amount_usdt,
            "payout_multiplier": payout_multiplier,
            "potential_win": potential_win,
            "strike_price": self.target_strike_price,
            "ref_at_entry": self.live_btc_price,
            "timestamp": time.time(),
            "is_real": self.is_real,
            "order_data": order_data
        }
        self.active_positions.append(pos)
        return {"success": True, "msg": f"Order {direction} terpasang"}

    def _resolve_round(self, final_price: float):
        """Menyelesaikan ronde. Pada mode Real, diverifikasi via Chainlink Oracle Binance SAPI"""
        if not self.active_positions:
            return

        if not self.is_real:
            # Mode Simulasi: evaluasi lokal berbasis perbandingan harga spot vs strike
            winning_dir = "Naik" if final_price >= self.target_strike_price else "Turun"
            
            remaining = []
            for pos in self.active_positions:
                won = (pos["direction"] == winning_dir)
                payout = pos["potential_win"] if won else 0.0
                profit = round(payout - pos["amount"], 2)

                self.virtual_balance = round(self.virtual_balance + payout, 2)
                self._save_virtual_balance()

                # Hitung kekalahan berturut-turut untuk proteksi cooldown
                if won:
                    self.consecutive_losses = 0
                else:
                    self.consecutive_losses += 1
                    if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSS:
                        self.cooldown_rounds_left = config.COOLDOWN_ROUNDS
                        self.last_cooldown_loss_id = pos.get("expiry_str")

                self.history.append({
                    "round": pos["expiry_str"][-8:],
                    "direction": pos["direction"],
                    "won": won,
                    "profit": profit,
                    "payout": payout,
                    "strike": pos.get("strike_price"),
                    "final_price": final_price,
                    "is_real": False,
                    "end_timestamp": time.time()
                })

            self.active_positions = remaining
            self._save_history()
        else:
            # Mode Real: pindahkan ke pending_settlement untuk verifikasi resmi on-chain Binance
            for pos in self.active_positions:
                pos["resolution_submitted_at"] = time.time()
                self.pending_settlement.append(pos)
            self.active_positions = []

            # Lakukan pengecekan awal
            self._check_pending_settlements()

    def _check_pending_settlements(self):
        """
        Memeriksa status penyelesaian (settlement) resmi dari Binance SAPI untuk posisi real.
        Mengecek posisi menang di position/filter (PENDING_CLAIM) dan posisi kalah di settled-history.
        """
        if not self.is_real or not self.pending_settlement:
            return

        try:
            pending_claim_list = self.client.get_pending_claim_positions()
        except Exception:
            pending_claim_list = []

        try:
            settled_list = self.client.get_real_settled_history(limit=10)
        except Exception:
            settled_list = []

        still_pending = []
        has_new_resolution = False
        existing_pos_ids = {h.get("position_id") for h in self.history if h.get("position_id")}

        for pending in self.pending_settlement:
            matched = None
            is_from_pending_claim = False
            pending_exp_ts = pending.get("expiry_timestamp", 0)
            pending_round_str = pending.get("expiry_str", "")[-8:]
            target_up = (pending["direction"] == "Naik")

            # 1. Periksa dulu di daftar posisi menang/klaim (position/filter)
            for pc in pending_claim_list:
                pc_id = pc.get("positionId")
                if pc_id and pc_id in existing_pos_ids:
                    continue

                # KUNCI UTAMA: Hanya proses jika posisi sudah resmi diselesaikan oleh Oracle Chainlink!
                status = str(pc.get("positionStatus", "")).upper()
                final_outcome = pc.get("finalOutcome")
                # Jika status masih ACTIVE/REGISTERED dan finalOutcome masih kosong, oracle belum selesai (tunggu 5-35s)
                if status not in ["PENDING_CLAIM", "CLAIMED", "SETTLED"] and not final_outcome:
                    continue

                pc_end_ts = pc.get("endDate", 0) / 1000.0
                pc_round_str = datetime.fromtimestamp(pc_end_ts).strftime("%H:%M:%S")
                pc_up = (pc.get("outcomeName") == "Up")

                if (abs(pc_end_ts - pending_exp_ts) <= 60 or pc_round_str == pending_round_str) and (target_up == pc_up):
                    matched = pc
                    is_from_pending_claim = True
                    break

            # 2. Jika tidak ada di pending_claim, cari di riwayat settled resmi Binance
            if not matched:
                for s in settled_list:
                    s_id = s.get("positionId")
                    if s_id and s_id in existing_pos_ids:
                        continue

                    # Pastikan status posisi settled resmi sudah selesai
                    s_status = str(s.get("positionStatus", "")).upper()
                    if s_status and s_status not in ["SETTLED", "CLAIMED"] and not s.get("finalOutcome"):
                        continue

                    s_end_ts = s.get("endDate", 0) / 1000.0
                    s_round_str = datetime.fromtimestamp(s_end_ts).strftime("%H:%M:%S")
                    s_up = (s.get("outcomeName") == "Up")

                    if (abs(s_end_ts - pending_exp_ts) <= 60 or s_round_str == pending_round_str) and (target_up == s_up):
                        matched = s
                        is_from_pending_claim = False
                        break

            if matched:
                has_new_resolution = True
                if matched.get("isWinner") is not None:
                    won = bool(matched.get("isWinner"))
                else:
                    target_name = "Up" if pending["direction"] == "Naik" else "Down"
                    won = (str(matched.get("finalOutcome", "")).capitalize() == target_name)

                raw_pnl = matched.get("realizedPnl")
                amount = round(float(matched.get("totalCost", pending["amount"])), 2)

                if raw_pnl is not None and float(raw_pnl) != 0:
                    profit = round(float(raw_pnl), 2)
                    payout = round(amount + profit, 2) if won else 0.0
                elif is_from_pending_claim:
                    shares = float(matched.get("shares", 0.0))
                    payout = shares if won else 0.0
                    profit = round(payout - amount, 2)
                else:
                    profit = round(float(matched.get("realizedPnl", 0.0)), 2)
                    if profit == 0.0 and not won:
                        profit = -amount
                    payout = round(amount + profit, 2) if won else 0.0

                # Otomatis klaim kemenangan ke saldo wallet on-chain jika belum di-klaim
                if won and matched.get("canClaim") and matched.get("tokenId"):
                    self.client.claim_prediction_winnings([matched["tokenId"]])

                if won:
                    self.consecutive_losses = 0
                else:
                    self.consecutive_losses += 1
                    if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSS:
                        self.cooldown_rounds_left = config.COOLDOWN_ROUNDS
                        self.last_cooldown_loss_id = matched.get("positionId")

                self.history.append({
                    "round": pending_round_str,
                    "direction": pending["direction"],
                    "won": won,
                    "profit": profit,
                    "payout": payout,
                    "amount": amount,
                    "strike": pending.get("strike_price"),
                    "final_price": matched.get("finalOutcome"),
                    "is_real": True,
                    "position_id": matched.get("positionId"),
                    "market_title": matched.get("marketTopicTitle"),
                    "end_timestamp": time.time()
                })
            else:
                # Cek apakah sudah timeout (> 240 detik / 4 menit dari waktu penyelesaian diajukan)
                elapsed = time.time() - pending.get("resolution_submitted_at", time.time())
                if elapsed > 240:
                    # Fallback jika Binance SAPI sangat lambat merespon
                    has_new_resolution = True
                    final_p = self.live_btc_price
                    target_strike = pending.get("strike_price") or final_p
                    won = (pending["direction"] == "Naik" and final_p >= target_strike) or \
                          (pending["direction"] == "Turun" and final_p < target_strike)
                    payout = pending["potential_win"] if won else 0.0
                    profit = round(payout - pending["amount"], 2)

                    if won:
                        self.consecutive_losses = 0
                    else:
                        self.consecutive_losses += 1
                        if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSS:
                            self.cooldown_rounds_left = config.COOLDOWN_ROUNDS
                            self.last_cooldown_loss_id = pending.get("position_id")

                    self.history.append({
                        "round": pending_round_str,
                        "direction": pending["direction"],
                        "won": won,
                        "profit": profit,
                        "payout": payout,
                        "amount": pending["amount"],
                        "strike": target_strike,
                        "final_price": final_p,
                        "is_real": True,
                        "fallback": True,
                        "end_timestamp": time.time()
                    })
                else:
                    still_pending.append(pending)

        self.pending_settlement = still_pending

        if has_new_resolution:
            self._save_history()
            try:
                self.get_balance(force_refresh=True)
            except Exception:
                pass

