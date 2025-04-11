import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load Discord tokens from .env
discord_tokens_env = os.getenv('DISCORD_TOKENS', '')
if not discord_tokens_env:
    raise ValueError("No Discord token found! Please set DISCORD_TOKENS in .env.")
discord_tokens = [token.strip() for token in discord_tokens_env.split(',') if token.strip()]
TOKEN = discord_tokens[0] if discord_tokens else None

# Load channel IDs from .env
channel_ids_env = os.getenv('CHANNEL_IDS', '')
if not channel_ids_env:
    raise ValueError("No channel IDs found! Please set CHANNEL_IDS in .env.")
channel_ids = [int(cid.strip()) for cid in channel_ids_env.split(',') if cid.strip()]
QUIZ_CHANNEL_ID = channel_ids[0] if channel_ids else None

# Load Google API keys
google_api_keys_env = os.getenv('GOOGLE_API_KEYS', '')
if not google_api_keys_env:
    raise ValueError("No Google API Key found! Please set GOOGLE_API_KEYS in .env.")
google_api_keys = [key.strip() for key in google_api_keys_env.split(',') if key.strip()]
GEMINI_API_KEY = google_api_keys[0] if google_api_keys else None

# Quiz configuration
QUIZ_MODERATOR = "imonjack"

# Initialize environment variables
load_dotenv()

# Load Discord tokens from .env
discord_tokens_env = os.getenv('DISCORD_TOKENS', '')
if discord_tokens_env:
    discord_tokens = [token.strip() for token in discord_tokens_env.split(',') if token.strip()]
else:
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        raise ValueError("No Discord token found! Please set DISCORD_TOKENS or DISCORD_TOKEN in .env.")
    discord_tokens = [discord_token]

# Load channel IDs from .env
channel_ids_env = os.getenv('CHANNEL_IDS', '')
if not channel_ids_env:
    raise ValueError("No channel IDs found! Please set CHANNEL_IDS in .env.")
channel_ids = [cid.strip() for cid in channel_ids_env.split(',') if cid.strip()]

# Load Google API keys
google_api_keys = os.getenv('GOOGLE_API_KEYS', '').split(',')
google_api_keys = [key.strip() for key in google_api_keys if key.strip()]
if not google_api_keys:
    raise ValueError("No Google API Key found! Please set GOOGLE_API_KEYS in .env.")

# Bot account information
bot_accounts = {}

# Global variables for moderation
MODERATION_KEYWORDS = [
    "don't type", "no messaging", "please stop texting", "don't chat here",
    "stop messaging", "no typing allowed", "quiet mode activated",
    "stop typing", "no chat", "silence", "quiet", "stop talking"
]

MODERATOR_ROLES = ["admin", "mod", "moderator", "staff", "owner", "MMT MOD", "MSAFE | OWNER"]
channel_coolds = {}  # Store cooldown end times for each channel
channel_cooldown_duration = 300  # Default cooldown duration in seconds (5 minutes)
channel_regular_message_counts = {}  # Track regular user message counts per channel
REQUIRED_REGULAR_MESSAGES = 50  # Number of regular user messages required to exit cooldown

# Message tracking variables
processed_messages_by_token = {}  # Track processed messages per token
message_distribution_lock = None  # Will be initialized in bot.py
token_message_queues = {}  # Message queues for each token
token_last_process_time = {}  # Track last process time for each token
TOKEN_DELAY = 5  # 5 second delay between tokens
token_message_counters = {}  # Track message counters per token

# Bot operation variables
bot_message_ids = set()  # Track IDs of messages sent by the bot
used_api_keys = set()
last_generated_text = None
cooldown_time = 86400 