"""
Bridge entrypoint for Binance BTCUSDT 5-Minute Prediction Bot.
Memungkinkan menjalankan bot melalui 'python3 bot.py' maupun 'python3 main.py'.
"""
from main import BtcPredictionApp

if __name__ == "__main__":
    app = BtcPredictionApp()
    app.run()
