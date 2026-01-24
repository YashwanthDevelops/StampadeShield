"""
TELEGRAM ALERT SYSTEM
Sends alerts to your phone
"""

import requests
from datetime import datetime


class TelegramAlert:
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.last_alert_time = None
        self.cooldown = 30  # Seconds between alerts
    
    def send_message(self, message):
        """Send message to Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"  Telegram error: {e}")
            return False
    
    def can_send(self):
        """Check if cooldown has passed"""
        if self.last_alert_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_alert_time).total_seconds()
        return elapsed >= self.cooldown
    
    def send_alert(self, level, risk, cpi, recommendation, factors):
        """Send formatted alert"""
        
        if not self.can_send():
            return False
        
        # Emoji based on level
        emoji = {
            "SAFE": "🟢",
            "LOW": "🟡",
            "MODERATE": "🟠",
            "HIGH": "🔴",
            "CRITICAL": "🚨"
        }
        
        # Build message
        msg = f"{emoji.get(level, '⚪')} <b>STAMPEDE ALERT</b>\n"
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        msg += f"<b>Level:</b> {level}\n"
        msg += f"<b>Risk:</b> {risk}%\n"
        msg += f"<b>CPI:</b> {cpi}\n"
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        msg += f"<b>Factors:</b>\n"
        
        for factor in factors[:3]:
            msg += f"• {factor}\n"
        
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        msg += f"<b>{recommendation}</b>\n"
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        msg += f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        
        success = self.send_message(msg)
        
        if success:
            self.last_alert_time = datetime.now()
            print("  📱 Telegram alert sent!")
        
        return success
    
    def send_startup(self):
        """Send startup message"""
        msg = "🚨 <b>STAMPEDE SYSTEM ONLINE</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━\n"
        msg += "✅ All nodes connected\n"
        msg += "✅ Monitoring started\n"
        msg += f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        
        return self.send_message(msg)