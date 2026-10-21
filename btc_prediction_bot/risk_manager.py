from typing import Dict, Any, Optional
import config

class RiskManager:
    """
    Manajer Risiko Kuantitatif (Risk & Position Sizing Engine).
    Menerapkan:
    - Zero-Martingale Policy (Dilarang melipatgandakan posisi saat rugi).
    - ATR-based Stop Loss & Take Profit.
    - Kill Switch jika drawdown sesi melebihi batas.
    - Pembatasan posisi aktif (Maksimal 1 posisi).
    - Blokade eksekusi ketat jika mode adalah SIGNAL_ONLY.
    """

    def __init__(self, initial_capital: float = 100.0):
        self.initial_capital = initial_capital
        self.peak_capital = initial_capital
        self.current_capital = initial_capital
        self.active_positions_count = 0
        self.is_kill_switch_triggered = False

    def validate_trade_allowed(
        self,
        prediction: str,
        current_spread: float,
        current_atr: float
    ) -> Dict[str, Any]:
        """Memvalidasi apakah pembukaan posisi baru diizinkan oleh aturan risiko"""
        # 1. Mode SIGNAL_ONLY tidak pernah boleh mengeksekusi order
        if config.TRADING_MODE == "SIGNAL_ONLY":
            return {
                "allowed": False,
                "reason": "Mode saat ini adalah SIGNAL_ONLY (Hanya analisis dan prediksi, eksekusi dinonaktifkan)."
            }

        # 2. Cek status Kill Switch
        if self.is_kill_switch_triggered:
            return {
                "allowed": False,
                "reason": "KILL SWITCH AKTIF: Batas maksimal drawdown terlampaui. Trading dihentikan otomatis."
            }

        # 3. Cek jumlah posisi aktif
        if self.active_positions_count >= config.MAX_ACTIVE_POSITIONS:
            return {
                "allowed": False,
                "reason": f"Posisi aktif sudah mencapai batas maksimal ({config.MAX_ACTIVE_POSITIONS})."
            }

        # 4. Filter Spread Melebar
        if current_spread > config.MAX_SPREAD_USDT:
            return {
                "allowed": False,
                "reason": f"Spread pasar melebar (${current_spread:.2f} > ${config.MAX_SPREAD_USDT:.2f})."
            }

        # 5. Filter Volatilitas Minimal
        if current_atr < config.MIN_ATR_THRESHOLD:
            return {
                "allowed": False,
                "reason": f"ATR terlalu rendah (${current_atr:.2f} < ${config.MIN_ATR_THRESHOLD:.2f})."
            }

        # 6. Sinyal harus tegas UP atau DOWN
        if prediction not in ["UP", "DOWN"]:
            return {
                "allowed": False,
                "reason": "Prediksi berstatus NEUTRAL."
            }

        return {"allowed": True, "reason": "Semua syarat manajemen risiko terpenuhi."}

    def calculate_levels_and_size(
        self,
        direction: str,
        entry_price: float,
        atr: float,
        account_balance: float
    ) -> Dict[str, float]:
        """
        Menghitung level Stop Loss, Take Profit, dan Nominal Posisi berdasarkan ATR.
        Anti-Martingale: Ukuran risiko selalu tetap (1% per trade).
        """
        sl_distance = config.STOP_LOSS_ATR_MULT * atr
        tp_distance = config.TAKE_PROFIT_ATR_MULT * atr

        if direction == "UP":
            sl_price = round(entry_price - sl_distance, 2)
            tp_price = round(entry_price + tp_distance, 2)
        else: # DOWN
            sl_price = round(entry_price + sl_distance, 2)
            tp_price = round(entry_price - tp_distance, 2)

        # Risk amount in USDT (misal 1% dari modal)
        risk_budget_usdt = account_balance * (config.RISK_PER_TRADE_PERCENT / 100.0)
        
        # Position size in BTC based on SL distance
        sl_percent = (sl_distance / entry_price) if entry_price > 0 else 0.01
        pos_value_usdt = (risk_budget_usdt / sl_percent) if sl_percent > 0 else 0.0
        
        # Batasi ukuran posisi agar tidak melebihi leverage maksimum
        max_notional = account_balance * config.DEFAULT_LEVERAGE
        actual_notional = min(pos_value_usdt, max_notional)
        quantity_btc = round(actual_notional / entry_price, 4) if entry_price > 0 else 0.0

        return {
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "sl_distance": round(sl_distance, 2),
            "tp_distance": round(tp_distance, 2),
            "risk_reward_ratio": round(tp_distance / sl_distance, 2) if sl_distance > 0 else 1.33,
            "quantity_btc": quantity_btc,
            "notional_usdt": round(actual_notional, 2),
            "leverage": config.DEFAULT_LEVERAGE
        }

    def update_capital(self, new_balance: float) -> None:
        """Memperbarui modal dan mengecek drawdown untuk aktivasi kill switch"""
        self.current_capital = new_balance
        if new_balance > self.peak_capital:
            self.peak_capital = new_balance

        drawdown = (self.peak_capital - new_balance) / self.peak_capital if self.peak_capital > 0 else 0.0
        if drawdown >= config.KILL_SWITCH_DRAWDOWN:
            self.is_kill_switch_triggered = True
