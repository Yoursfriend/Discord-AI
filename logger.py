import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from colorama import Fore, Style
from config import discord_tokens, bot_accounts  # Import from config instead of bot

class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels"""
    COLORS = {
        'DEBUG': Fore.BLUE,
        'INFO': Fore.CYAN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
        'SUCCESS': Fore.GREEN,
        'TIMESTAMP': Fore.MAGENTA,
        'CHANNEL': Fore.BLUE,
        'BOT': Fore.GREEN,
        'SERVER': Fore.YELLOW,
        'MESSAGE': Fore.WHITE,
        'BORDER': Fore.MAGENTA
    }
    ICONS = {
        'DEBUG': '🔍',
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '🚨',
        'CRITICAL': '💥',
        'SUCCESS': '✅',
        'WAIT': '⌛',
        'BOT': '🤖',
        'SERVER': '🌐',
        'CHANNEL': '📝',
        'MESSAGE': '💬'
    }
    def format(self, record):
        original_msg = record.msg
        if record.levelname == 'SUCCESS':
            record.levelname = 'SUCCESS'
        level_color = self.COLORS.get(record.levelname, Fore.WHITE)
        icon = self.ICONS.get(record.levelname, '')
        timestamp_color = self.COLORS['TIMESTAMP']
        record.created_fmt = f"{timestamp_color}{self.formatTime(record)}{Style.RESET_ALL}"
        level_str = f"{level_color}[{record.levelname}]{Style.RESET_ALL}"
        if '[Channel' in original_msg:
            parts = original_msg.split(']', 1)
            channel_part = parts[0] + ']'
            message_part = parts[1] if len(parts) > 1 else ''
            channel_part = channel_part.replace('[Channel', f"{self.COLORS['CHANNEL']}[Channel{Style.RESET_ALL}")
            if 'Connected to server' in message_part:
                message_part = f"{self.ICONS['SERVER']} {message_part}"
            elif 'Bot active' in message_part:
                message_part = f"{self.ICONS['BOT']} {message_part}"
            elif 'Message sent' in message_part or 'Message received' in message_part:
                message_part = f"{self.ICONS['MESSAGE']} {message_part}"
            record.msg = f"{channel_part}{message_part}"
        record.msg = f"{level_color}{icon} {record.msg}{Style.RESET_ALL}"
        formatted = super().format(record)
        if record.levelname in ['ERROR', 'CRITICAL', 'SUCCESS']:
            border = f"{self.COLORS['BORDER']}{'=' * 80}{Style.RESET_ALL}"
            formatted = f"\n{border}\n{formatted}\n{border}\n"
        return formatted

def setup_logging():
    """Setup logging configuration"""
    if not os.path.exists('logs'):
        os.makedirs('logs')
    log_format = '%(asctime)s [%(levelname)s] %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    logger = logging.getLogger('DiscordBot')
    logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    if sys.platform == 'win32':
        console_handler.stream.reconfigure(encoding='utf-8')
    console_formatter = ColoredFormatter(log_format, date_format)
    console_handler.setFormatter(console_formatter)
    file_handler = RotatingFileHandler(
        'logs/discord_bot.log',
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(log_format, date_format)
    file_handler.setFormatter(file_formatter)
    error_handler = RotatingFileHandler(
        'logs/error.log',
        maxBytes=5*1024*1024,
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    return logger

def format_message(message, level="INFO", channel_id=None, bot_username=None):
    """Format message with appropriate styling and bot information"""
    if channel_id:
        # Always add bot username to channel messages if available
        if bot_username:
            message = f"[Channel {channel_id} | Bot: {bot_username}] {message}"
        else:
            message = f"[Channel {channel_id}] {message}"
            
        # Bot status and operation messages
        if "Bot is running on multiple servers" in message:
            message = f"{Fore.GREEN}🚀 BOT STATUS:{Style.RESET_ALL} {Fore.CYAN}{message}{Style.RESET_ALL}"
            message = f"\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}"
        elif "Waiting" in message and "before reading messages" in message:
            message = f"{Fore.YELLOW}⏳ WAITING:{Style.RESET_ALL} {Fore.CYAN}{message}{Style.RESET_ALL}"
            message = f"\n{Fore.YELLOW}{'─' * 80}{Style.RESET_ALL}\n{message}\n{Fore.YELLOW}{'─' * 80}{Style.RESET_ALL}"
        elif "Received:" in message:
            content = message.split("Received:")[1].strip()
            message = f"{Fore.GREEN}📥 RECEIVED:{Style.RESET_ALL} {Fore.WHITE}{content}{Style.RESET_ALL}"
            message = f"\n{Fore.GREEN}{'─' * 80}{Style.RESET_ALL}\n{message}\n{Fore.GREEN}{'─' * 80}{Style.RESET_ALL}"
        elif "Slow mode delay:" in message:
            delay = message.split("Slow mode delay:")[1].strip()
            message = f"{Fore.MAGENTA}⏱️ SLOW MODE:{Style.RESET_ALL} {Fore.CYAN}Delay set to {delay}{Style.RESET_ALL}"
            message = f"\n{Fore.MAGENTA}{'─' * 80}{Style.RESET_ALL}\n{message}\n{Fore.MAGENTA}{'─' * 80}{Style.RESET_ALL}"
        elif "Slow mode active" in message:
            message = f"{Fore.MAGENTA}⏳ SLOW MODE:{Style.RESET_ALL} {Fore.CYAN}{message}{Style.RESET_ALL}"
            message = f"\n{Fore.MAGENTA}{'─' * 80}{Style.RESET_ALL}\n{message}\n{Fore.MAGENTA}{'─' * 80}{Style.RESET_ALL}"
        # Moderation-specific formatting
        elif "Moderation message detected" in message:
            message = f"🛡️ {Fore.RED}MODERATION:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.RED}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.RED}{'═' * 80}{Style.RESET_ALL}"
        elif "Entering cooldown mode" in message:
            message = f"⏸️ {Fore.YELLOW}COOLDOWN:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.YELLOW}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.YELLOW}{'═' * 80}{Style.RESET_ALL}"
        elif "Exiting cooldown mode" in message:
            message = f"▶️ {Fore.GREEN}COOLDOWN END:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}"
        elif "Regular message count" in message:
            message = f"📊 {Fore.CYAN}MESSAGE COUNT:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.CYAN}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.CYAN}{'═' * 80}{Style.RESET_ALL}"
        elif "Waiting for" in message and "more regular messages" in message:
            message = f"⏳ {Fore.MAGENTA}COOLDOWN STATUS:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.MAGENTA}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.MAGENTA}{'═' * 80}{Style.RESET_ALL}"
        elif "In cooldown mode" in message:
            message = f"🔒 {Fore.YELLOW}COOLDOWN:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.YELLOW}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.YELLOW}{'═' * 80}{Style.RESET_ALL}"
        # Regular operation formatting
        elif "Bot active:" in message:
            message = f"🚀 {Fore.GREEN}BOT STATUS:{Style.RESET_ALL} {Fore.CYAN}{message}{Style.RESET_ALL}"
            message = f"\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}"
        elif "Message sent:" in message:
            message = f"📤 {Fore.GREEN}SENT:{Style.RESET_ALL} {Fore.CYAN}{message.split('Message sent:')[1]}{Style.RESET_ALL}"
            message = f"\n{Fore.GREEN}{'─' * 80}{Style.RESET_ALL}\n{message}\n{Fore.GREEN}{'─' * 80}{Style.RESET_ALL}"
        elif "Waiting" in message and "before next iteration" in message:
            message = f"⏰ {Fore.BLUE}NEXT ITERATION:{Style.RESET_ALL} {Fore.CYAN}{message}{Style.RESET_ALL}"
            message = f"\n{Fore.BLUE}{'─' * 80}{Style.RESET_ALL}\n{message}\n{Fore.BLUE}{'─' * 80}{Style.RESET_ALL}"
        # Existing formatting
        elif "Settings:" in message:
            message = f"⚙️ {message}"
        elif "Error" in message or "Failed" in message:
            message = f"❌ {Fore.RED}ERROR:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.RED}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.RED}{'═' * 80}{Style.RESET_ALL}"
        elif "Success" in message:
            message = f"✅ {Fore.GREEN}SUCCESS:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}"
        elif "No new messages" in message:
            message = f"🔍 {Fore.YELLOW}STATUS:{Style.RESET_ALL} {message}"
        elif "Analyzing server" in message:
            message = f"🔎 {Fore.CYAN}ANALYSIS:{Style.RESET_ALL} {message}"
        elif "Analysis complete" in message:
            message = f"💡 {Fore.GREEN}ANALYSIS:{Style.RESET_ALL} {message}"
        
        if "Settings:" in message:
            parts = message.split("Settings:")
            message = f"{parts[0]}{Fore.CYAN}Settings:{Style.RESET_ALL}"
            settings = parts[1].split(", ")
            colored_settings = []
            for setting in settings:
                if "=" in setting:
                    key, value = setting.split("=")
                    if "Active" in value:
                        value = f"{Fore.GREEN}Active{Style.RESET_ALL}"
                    elif "No" in value:
                        value = f"{Fore.RED}No{Style.RESET_ALL}"
                    elif "Yes" in value:
                        value = f"{Fore.GREEN}Yes{Style.RESET_ALL}"
                    elif "seconds" in value:
                        value = f"{Fore.YELLOW}{value}{Style.RESET_ALL}"
                    colored_settings.append(f"{Fore.GREEN}{key.strip()}{Style.RESET_ALL} = {value}")
            message += " " + ", ".join(colored_settings)
    
    return message

def log_message(message, level="INFO", channel_id=None):
    """Log a message with appropriate formatting and level"""
    if channel_id:
        # Get bot username for this channel
        bot_username = None
        try:
            for token in discord_tokens:
                bot_info = bot_accounts.get(token, {})
                if bot_info.get("username"):
                    bot_username = bot_info["username"]
                    break
        except (NameError, AttributeError):
            # If variables are not available, just use channel ID
            message = f"[Channel {channel_id}] {message}"
        else:
            # Always add bot username to channel messages
            message = f"[Channel {channel_id} | Bot: {bot_username}] {message}"
            
        # Bot status and operation messages
        if "Bot is running on multiple servers" in message:
            message = f"{Fore.GREEN}🚀 BOT STATUS:{Style.RESET_ALL} {Fore.CYAN}{message}{Style.RESET_ALL}"
            message = f"\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}"
        elif "Initial delay of" in message:
            message = f"{Fore.YELLOW}⏳ INITIAL DELAY:{Style.RESET_ALL} {Fore.CYAN}{message}{Style.RESET_ALL}"
            message = f"\n{Fore.YELLOW}{'─' * 80}{Style.RESET_ALL}\n{message}\n{Fore.YELLOW}{'─' * 80}{Style.RESET_ALL}"
        elif "Waiting" in message and "before reading messages" in message:
            message = f"{Fore.YELLOW}⏳ WAITING:{Style.RESET_ALL} {Fore.CYAN}{message}{Style.RESET_ALL}"
            message = f"\n{Fore.YELLOW}{'─' * 80}{Style.RESET_ALL}\n{message}\n{Fore.YELLOW}{'─' * 80}{Style.RESET_ALL}"
        elif "Received:" in message:
            content = message.split("Received:")[1].strip()
            message = f"{Fore.GREEN}📥 RECEIVED:{Style.RESET_ALL} {Fore.WHITE}{content}{Style.RESET_ALL}"
            message = f"\n{Fore.GREEN}{'─' * 80}{Style.RESET_ALL}\n{message}\n{Fore.GREEN}{'─' * 80}{Style.RESET_ALL}"
        elif "Slow mode delay:" in message:
            delay = message.split("Slow mode delay:")[1].strip()
            message = f"{Fore.MAGENTA}⏱️ SLOW MODE:{Style.RESET_ALL} {Fore.CYAN}Delay set to {delay}{Style.RESET_ALL}"
            message = f"\n{Fore.MAGENTA}{'─' * 80}{Style.RESET_ALL}\n{message}\n{Fore.MAGENTA}{'─' * 80}{Style.RESET_ALL}"
        elif "Slow mode active" in message:
            message = f"{Fore.MAGENTA}⏳ SLOW MODE:{Style.RESET_ALL} {Fore.CYAN}{message}{Style.RESET_ALL}"
            message = f"\n{Fore.MAGENTA}{'─' * 80}{Style.RESET_ALL}\n{message}\n{Fore.MAGENTA}{'─' * 80}{Style.RESET_ALL}"
        # Moderation-specific formatting
        elif "Moderation message detected" in message:
            message = f"🛡️ {Fore.RED}MODERATION:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.RED}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.RED}{'═' * 80}{Style.RESET_ALL}"
        elif "Entering cooldown mode" in message:
            message = f"⏸️ {Fore.YELLOW}COOLDOWN:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.YELLOW}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.YELLOW}{'═' * 80}{Style.RESET_ALL}"
        elif "Exiting cooldown mode" in message:
            message = f"▶️ {Fore.GREEN}COOLDOWN END:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}"
        elif "Regular message count" in message:
            message = f"📊 {Fore.CYAN}MESSAGE COUNT:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.CYAN}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.CYAN}{'═' * 80}{Style.RESET_ALL}"
        elif "Waiting for" in message and "more regular messages" in message:
            message = f"⏳ {Fore.MAGENTA}COOLDOWN STATUS:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.MAGENTA}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.MAGENTA}{'═' * 80}{Style.RESET_ALL}"
        elif "In cooldown mode" in message:
            message = f"🔒 {Fore.YELLOW}COOLDOWN:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.YELLOW}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.YELLOW}{'═' * 80}{Style.RESET_ALL}"
        # Regular operation formatting
        elif "Bot active:" in message:
            message = f"🚀 {Fore.GREEN}BOT STATUS:{Style.RESET_ALL} {Fore.CYAN}{message}{Style.RESET_ALL}"
            message = f"\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}"
        elif "Message sent:" in message:
            message = f"📤 {Fore.GREEN}SENT:{Style.RESET_ALL} {Fore.CYAN}{message.split('Message sent:')[1]}{Style.RESET_ALL}"
            message = f"\n{Fore.GREEN}{'─' * 80}{Style.RESET_ALL}\n{message}\n{Fore.GREEN}{'─' * 80}{Style.RESET_ALL}"
        elif "Waiting" in message and "before next iteration" in message:
            message = f"⏰ {Fore.BLUE}NEXT ITERATION:{Style.RESET_ALL} {Fore.CYAN}{message}{Style.RESET_ALL}"
            message = f"\n{Fore.BLUE}{'─' * 80}{Style.RESET_ALL}\n{message}\n{Fore.BLUE}{'─' * 80}{Style.RESET_ALL}"
        # Existing formatting
        elif "Settings:" in message:
            message = f"⚙️ {message}"
        elif "Error" in message or "Failed" in message:
            message = f"❌ {Fore.RED}ERROR:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.RED}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.RED}{'═' * 80}{Style.RESET_ALL}"
        elif "Success" in message:
            message = f"✅ {Fore.GREEN}SUCCESS:{Style.RESET_ALL} {message}"
            message = f"\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}\n{message}\n{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}"
        elif "No new messages" in message:
            message = f"🔍 {Fore.YELLOW}STATUS:{Style.RESET_ALL} {message}"
        elif "Analyzing server" in message:
            message = f"🔎 {Fore.CYAN}ANALYSIS:{Style.RESET_ALL} {message}"
        elif "Analysis complete" in message:
            message = f"💡 {Fore.GREEN}ANALYSIS:{Style.RESET_ALL} {message}"
        
        if "Settings:" in message:
            parts = message.split("Settings:")
            message = f"{parts[0]}{Fore.CYAN}Settings:{Style.RESET_ALL}"
            settings = parts[1].split(", ")
            colored_settings = []
            for setting in settings:
                if "=" in setting:
                    key, value = setting.split("=")
                    if "Active" in value:
                        value = f"{Fore.GREEN}Active{Style.RESET_ALL}"
                    elif "No" in value:
                        value = f"{Fore.RED}No{Style.RESET_ALL}"
                    elif "Yes" in value:
                        value = f"{Fore.GREEN}Yes{Style.RESET_ALL}"
                    elif "seconds" in value:
                        value = f"{Fore.YELLOW}{value}{Style.RESET_ALL}"
                    colored_settings.append(f"{Fore.GREEN}{key.strip()}{Style.RESET_ALL} = {value}")
            message += " " + ", ".join(colored_settings)
    
    if level.upper() == "SUCCESS":
        logger.info(message)
    elif level.upper() == "ERROR":
        logger.error(message)
    elif level.upper() == "WARNING":
        logger.warning(message)
    elif level.upper() == "WAIT":
        logger.info(message)
    elif level.upper() == "DEBUG":
        logger.debug(message)
    else:
        logger.info(message)

# Initialize logger
logger = setup_logging() 