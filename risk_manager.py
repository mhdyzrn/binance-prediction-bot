from typing import Dict, Any, Optional
import config

class RiskManager:
    """
    Kalkulator sizing awal. Tidak mengotorisasi atau mengelola posisi exchange.
    Order tetap ditolak sampai tersedia executor dan sinkronisasi posisi/saldo.
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
        """Always refuse orders until exchange execution and position tracking exist."""
        return {
            "allowed": False,
            "reason": "Eksekusi Futures dinonaktifkan: order executor dan pelacakan posisi exchange belum tersedia."
        }

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
        if direction not in ("UP", "DOWN"):
            raise ValueError("direction harus UP atau DOWN")
        if entry_price <= 0 or atr <= 0 or account_balance <= 0:
            raise ValueError("entry_price, atr, dan account_balance harus lebih besar dari nol")
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
