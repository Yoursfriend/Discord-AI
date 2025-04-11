import json
import threading
import time
import os
import random
import re
import requests
from dotenv import load_dotenv
from datetime import datetime
from colorama import init, Fore, Style
from logger import log_message, logger
from config import (
    discord_tokens, channel_ids, google_api_keys, bot_accounts,
    MODERATION_KEYWORDS, MODERATOR_ROLES, channel_coolds,
    channel_cooldown_duration, channel_regular_message_counts,
    REQUIRED_REGULAR_MESSAGES, processed_messages_by_token,
    message_distribution_lock, token_message_queues,
    token_last_process_time, TOKEN_DELAY, token_message_counters,
    bot_message_ids, used_api_keys, last_generated_text, cooldown_time
)

# Initialize colorama and environment variables
init(autoreset=True)
load_dotenv()

# Load Discord tokens from .env
discord_tokens_env = os.getenv('DISCORD_TOKENS', '')
if discord_tokens_env:
    discord_tokens = [token.strip() for token in discord_tokens_env.split(',') if token.strip()]
else:
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        logger.critical("No Discord token found! Please set DISCORD_TOKENS or DISCORD_TOKEN in .env.")
        raise ValueError("No Discord token found! Please set DISCORD_TOKENS or DISCORD_TOKEN in .env.")
    discord_tokens = [discord_token]

# Load channel IDs from .env
channel_ids_env = os.getenv('CHANNEL_IDS', '')
if not channel_ids_env:
    logger.critical("No channel IDs found! Please set CHANNEL_IDS in .env.")
    raise ValueError("No channel IDs found! Please set CHANNEL_IDS in .env.")
channel_ids = [cid.strip() for cid in channel_ids_env.split(',') if cid.strip()]
logger.info(f"Loaded {len(channel_ids)} channels from .env")

# Load Google API keys
google_api_keys = os.getenv('GOOGLE_API_KEYS', '').split(',')
google_api_keys = [key.strip() for key in google_api_keys if key.strip()]
if not google_api_keys:
    logger.critical("No Google API Key found! Please set GOOGLE_API_KEYS in .env.")
    raise ValueError("No Google API Key found! Please set GOOGLE_API_KEYS in .env.")

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

# Add these global variables at the top with other globals
processed_messages_by_token = {}  # Track processed messages per token
message_distribution_lock = threading.Lock()  # Lock for thread-safe message distribution
token_message_queues = {}  # Message queues for each token
token_last_process_time = {}  # Track last process time for each token
TOKEN_DELAY = 5  # 5 second delay between tokens
token_message_counters = {}  # Track message counters per token

# Keep only necessary global variables
bot_message_ids = set()  # Track IDs of messages sent by the bot
used_api_keys = set()
last_generated_text = None
cooldown_time = 86400

# Load AI prompts from .env
AI_PROMPT_BASE = os.getenv('AI_PROMPT_BASE', '')
AI_PROMPT_PERSONALITY = os.getenv('AI_PROMPT_PERSONALITY', '')
AI_PROMPT_RESPONSE_STYLE = os.getenv('AI_PROMPT_RESPONSE_STYLE', '')
AI_PROMPT_SPECIAL_RULES = os.getenv('AI_PROMPT_SPECIAL_RULES', '')

# Default prompts if not set in .env
DEFAULT_AI_PROMPT_BASE = (
    "Chat context:\n{context}\n\n"
    "Analyze the above conversation. If you have enough context to form a proper reply to the following message, "
    "reply in 8-9 words using friendly, casual language. If not, respond with 'no reply'.\n\n"
    "Message: {prompt}\n\n"
)

DEFAULT_AI_PROMPT_PERSONALITY = (
    "Reply like you're a genuine, casual, friendly guy, chatting in a dating app, don't use emojis and slangs sometimes. "
    "Your response should be 8-9 words maximum, always in lowercase, with occasional typos, no commas, no exclamation marks and rarely any emojis. "
    "Avoid repeating words or phrases, dont use man, dude, yeah, totally, like, you know, etc repeatedly."
)

DEFAULT_AI_PROMPT_SPECIAL_RULES = (
    "If Question is about name, always reply asish kumar\n"
    "if question is about where are you from, always reply as india\n"
    "if question is about what you do, always reply as a college student\n"
    "if question is about you are a bot like this, reply should be in sarcastic way to prove you are a human\n"
    "RCB is royal challengers bangalore, its a cricket team and you are a fan of it\n"
    "if question is about your age, always reply as 21"
)

def log_message(message, level="INFO", channel_id=None):
    timestamp = datetime.now().strftime("%H:%M:%S")
    level_emoji = {
        "INFO": "ℹ️",
        "ERROR": "🚨",
        "SUCCESS": "✅",
        "WARNING": "⚠️",
        "WAIT": "⏳"
    }
    emoji = level_emoji.get(level, "ℹ️")
    
    # Remove channel ID and elapsed time from message
    message = re.sub(r'\[Channel \d+\]', '', message)
    message = re.sub(r'\[\d+\.\d+s\]', '', message)
    message = message.strip()
    
    print(f"{timestamp} {emoji} {message}")

def is_moderation_message(message):
    """Check if a message contains moderation keywords"""
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in MODERATION_KEYWORDS)

def is_moderator(user_roles):
    """Check if user has moderator roles"""
    user_roles_lower = [role.lower() for role in user_roles]
    return any(mod_role in user_roles_lower for mod_role in MODERATOR_ROLES)

def is_in_cooldown(channel_id):
    """Check if a channel is in cooldown mode"""
    if channel_id in channel_coolds:
        if time.time() < channel_coolds[channel_id]:
            return True
        else:
            # Check if enough regular messages have been received
            if channel_id in channel_regular_message_counts:
                if channel_regular_message_counts[channel_id] >= REQUIRED_REGULAR_MESSAGES:
                    log_message(f"[Channel {channel_id}] Exiting cooldown mode after receiving {REQUIRED_REGULAR_MESSAGES} regular messages.", "INFO")
                    del channel_coolds[channel_id]
                    del channel_regular_message_counts[channel_id]
                    return False
            return True
    return False

def set_channel_cooldown(channel_id, duration=None):
    """Set cooldown for a channel"""
    if duration is None:
        duration = channel_cooldown_duration
    channel_coolds[channel_id] = time.time() + duration
    channel_regular_message_counts[channel_id] = 0  # Reset regular message counter

def increment_regular_message_count(channel_id):
    """Increment the regular message counter for a channel"""
    if channel_id in channel_regular_message_counts:
        channel_regular_message_counts[channel_id] += 1
        log_message(f"[Channel {channel_id}] Regular message count: {channel_regular_message_counts[channel_id]}/{REQUIRED_REGULAR_MESSAGES}", "INFO")

def is_message_processed_by_token(message_id, token):
    """Check if a message has been processed by a specific token"""
    if token not in processed_messages_by_token:
        processed_messages_by_token[token] = set()
    return message_id in processed_messages_by_token[token]

def mark_message_processed_by_token(message_id, token):
    """Mark a message as processed by a specific token"""
    if token not in processed_messages_by_token:
        processed_messages_by_token[token] = set()
    processed_messages_by_token[token].add(message_id)

def get_random_api_key():
    available_keys = [key for key in google_api_keys if key not in used_api_keys]
    if not available_keys:
        log_message("All API keys have hit error 429. Waiting 24 hours before trying again...", "ERROR")
        time.sleep(cooldown_time)
        used_api_keys.clear()
        return get_random_api_key()
    return random.choice(available_keys)

def get_random_message_from_file():
    try:
        with open("chats.txt", "r", encoding="utf-8") as file:
            messages = [line.strip() for line in file.readlines() if line.strip()]
            return random.choice(messages) if messages else "No messages available in file."
    except FileNotFoundError:
        return "Message file chats.txt not found!"

def generate_language_specific_prompt(user_message, prompt_language):
    if prompt_language == 'en':
        return f"Reply to the following message in English: {user_message}"
    elif prompt_language == 'hi':
        return f"Reply to the following message in Hindi: {user_message}"
    else:
        log_message(f"Prompt language '{prompt_language}' is invalid. Message skipped.", "WARNING")
        return None

# NEW: Build conversation context from recent messages
def build_context(messages, num_messages=30):
    # Get up to num_messages and reverse so they are in chronological order
    recent_msgs = list(reversed(messages[:num_messages]))
    context_lines = []
    for msg in recent_msgs:
        author = msg.get('author', {}).get('username', 'unknown')
        content = msg.get('content', '').strip()
        if content:
            context_lines.append(f"{author}: {content}")
    return "\n".join(context_lines)

# Updated generate_reply including context analysis instructions
def generate_reply(prompt, prompt_language, use_google_ai=True, context=""):
    global last_generated_text
    if use_google_ai:
        google_api_key = get_random_api_key()
        lang_prompt = generate_language_specific_prompt(prompt, prompt_language)
        if lang_prompt is None:
            return None

        # Use environment variables if set, otherwise use defaults
        base_prompt = AI_PROMPT_BASE or DEFAULT_AI_PROMPT_BASE
        personality_prompt = AI_PROMPT_PERSONALITY or DEFAULT_AI_PROMPT_PERSONALITY
        special_rules = AI_PROMPT_SPECIAL_RULES or DEFAULT_AI_PROMPT_SPECIAL_RULES

        ai_prompt = (
            base_prompt.format(context=context, prompt=prompt) + "\n" +
            special_rules + "\n\n" +
            personality_prompt
        )

        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={google_api_key}'
        headers = {'Content-Type': 'application/json'}
        data = {'contents': [{'parts': [{'text': ai_prompt}]}]}
        while True:
            try:
                response = requests.post(url, headers=headers, json=data)
                if response.status_code == 429:
                    log_message(f"API key {google_api_key} hit rate limit (429). Using another API key...", "WARNING")
                    used_api_keys.add(google_api_key)
                    return generate_reply(prompt, prompt_language, use_google_ai, context)
                response.raise_for_status()
                result = response.json()
                generated_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                if generated_text == last_generated_text:
                    log_message("AI generated same text, requesting new text...", "WAIT")
                    continue
                last_generated_text = generated_text
                return generated_text
            except requests.exceptions.RequestException as e:
                log_message(f"Request failed: {e}", "ERROR")
                time.sleep(2)
    else:
        return get_random_message_from_file()

def get_channel_info(channel_id, token):
    headers = {'Authorization': token}
    channel_url = f"https://discord.com/api/v9/channels/{channel_id}"
    try:
        channel_response = requests.get(channel_url, headers=headers)
        channel_response.raise_for_status()
        channel_data = channel_response.json()
        channel_name = channel_data.get('name', 'Unknown Channel')
        guild_id = channel_data.get('guild_id')
        server_name = "Direct Message"
        if guild_id:
            guild_url = f"https://discord.com/api/v9/guilds/{guild_id}"
            guild_response = requests.get(guild_url, headers=headers)
            guild_response.raise_for_status()
            guild_data = guild_response.json()
            server_name = guild_data.get('name', 'Unknown Server')
        return server_name, channel_name
    except requests.exceptions.RequestException as e:
        log_message(f"Error getting channel info: {e}", "ERROR")
        return "Unknown Server", "Unknown Channel"

def get_bot_info(token):
    headers = {'Authorization': token}
    try:
        response = requests.get("https://discord.com/api/v9/users/@me", headers=headers)
        response.raise_for_status()
        data = response.json()
        username = data.get("username", "Unknown")
        discriminator = data.get("discriminator", "")
        bot_id = data.get("id", "Unknown")
        return username, discriminator, bot_id
    except requests.exceptions.RequestException as e:
        log_message(f"Failed to get bot account info: {e}", "ERROR")
        return "Unknown", "", "Unknown"

def get_token_index(token):
    """Get the index of the token to determine its delay"""
    for i, t in enumerate(discord_tokens):
        if t == token:
            return i
    return 0

def get_next_unprocessed_message(messages, token):
    """Get the next unprocessed message for a specific token"""
    with message_distribution_lock:
        if token not in token_message_counters:
            token_message_counters[token] = 0
            
        # Process messages based on token index and total number of tokens
        token_index = get_token_index(token)
        total_tokens = len(discord_tokens)
        
        for message in messages:
            message_id = message.get('id')
            if message_id not in processed_messages_by_token.get(token, set()):
                if token_message_counters[token] % total_tokens == token_index:
                    token_message_counters[token] += 1
                    return message
                token_message_counters[token] += 1
        return None

def is_direct_reply(message, bot_user_id):
    """Check if a message is a direct reply to the bot"""
    # Check message reference
    if message.get('message_reference'):
        referenced_message_id = message['message_reference'].get('message_id')
        if referenced_message_id in bot_message_ids:
            return True
    
    # Check mentions
    mentions = message.get('mentions', [])
    for mention in mentions:
        if mention.get('id') == bot_user_id:
            return True
    
    # Check content for @mentions
    content = message.get('content', '').lower()
    if f'<@{bot_user_id}>' in content:
        return True
    
    return False

def auto_reply(channel_id, settings, token):
    headers = {'Authorization': token}
    try:
        bot_info_response = requests.get('https://discord.com/api/v9/users/@me', headers=headers)
        bot_info_response.raise_for_status()
        bot_user_id = bot_info_response.json().get('id')
        bot_username = bot_info_response.json().get('username')
    except requests.exceptions.RequestException as e:
        log_message(f"[Channel {channel_id}] Failed to get bot info: {e}", "ERROR")
        return

    # Initialize timing variables
    if token not in token_last_process_time:
        token_last_process_time[token] = 0
    last_message_time = 0
    rate_limit_until = 0
    slow_mode_delay = 0
    start_time = time.time()

    # Get token index for delay calculation
    token_index = get_token_index(token)
    initial_delay = token_index * TOKEN_DELAY

    # Initial delay based on token index
    elapsed = time.time() - start_time
    log_message(f"[{bot_username}] Initial delay: {initial_delay}s (Token {token_index + 1})", "WAIT")
    time.sleep(initial_delay)

    while True:
        current_time = time.time()
        elapsed = current_time - start_time

        # Check rate limits first
        if current_time < rate_limit_until:
            wait_time = rate_limit_until - current_time
            log_message(f"[{bot_username}] Rate limit: {wait_time:.1f}s", "WAIT")
            time.sleep(wait_time)
            continue

        # Check cooldown mode
        if is_in_cooldown(channel_id):
            remaining_time = int(channel_coolds[channel_id] - current_time)
            if remaining_time > 0:
                log_message(f"[{bot_username}] Cooldown: {remaining_time}s", "WAIT")
            else:
                log_message(f"[{bot_username}] Waiting for {REQUIRED_REGULAR_MESSAGES - channel_regular_message_counts.get(channel_id, 0)} more messages", "WAIT")
            time.sleep(min(remaining_time if remaining_time > 0 else 60, 60))
            continue

        # Get current slow mode delay
        if settings["use_slow_mode"]:
            slow_mode_delay = get_slow_mode_delay(channel_id, token)
            slow_mode_delay += (token_index * TOKEN_DELAY)
            log_message(f"[{bot_username}] Slow mode: {slow_mode_delay}s", "INFO")

        # Add token-specific delay before reading messages
        read_delay = settings['read_delay'] + (token_index * TOKEN_DELAY)
        log_message(f"[{bot_username}] Reading in {read_delay}s", "WAIT")
        time.sleep(read_delay)

        try:
            response = requests.get(f'https://discord.com/api/v9/channels/{channel_id}/messages', headers=headers)
            response.raise_for_status()
            messages = response.json()

            # Process direct replies first
            direct_replies = []
            for message in messages:
                message_id = message.get('id')
                if message_id in processed_messages_by_token.get(token, set()):
                    continue
                author_id = message.get('author', {}).get('id')
                if author_id == bot_user_id:
                    continue

                # Check if this is a direct reply to this bot
                if is_direct_reply(message, bot_user_id):
                    user_message = message.get('content', '').strip()
                    if user_message and re.search(r'\w', user_message):
                        # Check if this message is a reply to this bot's message
                        with message_distribution_lock:
                            if message_id not in processed_messages_by_token.get(token, set()):
                                direct_replies.append({
                                    'message': message,
                                    'content': user_message,
                                    'id': message_id
                                })
                                mark_message_processed_by_token(message_id, token)
                                log_message(f"[{bot_username}] Reply: {user_message[:30]}...", "INFO")

            # Process direct replies with slow mode timing
            if direct_replies:
                for reply in direct_replies:
                    # Check rate limit before processing
                    if time.time() < rate_limit_until:
                        wait_time = rate_limit_until - time.time()
                        log_message(f"[{bot_username}] Rate limit: {wait_time:.1f}s", "WAIT")
                        time.sleep(wait_time)

                    # Apply slow mode delay if needed
                    if settings["use_slow_mode"]:
                        time_since_last = time.time() - last_message_time
                        if time_since_last < slow_mode_delay:
                            wait_time = slow_mode_delay - time_since_last
                            log_message(f"[{bot_username}] Slow mode: {wait_time:.1f}s", "WAIT")
                            time.sleep(wait_time)
                            last_message_time = time.time()

                    log_message(f"[{bot_username}] Processing: {reply['content'][:30]}...", "INFO")
                    prompt = reply['content']
                    reply_to_id = reply['id']

                    context = build_context(messages, num_messages=30)
                    result = generate_reply(prompt, settings["prompt_language"], settings["use_google_ai"], context)

                    if result is None:
                        log_message(f"[{bot_username}] Invalid language", "WARNING")
                    elif result.lower() == "no reply":
                        log_message(f"[{bot_username}] No context", "INFO")
                    else:
                        response_text = result if result else "sorry cannot reply"
                        if response_text.strip().lower() == prompt.strip().lower():
                            log_message(f"[{bot_username}] Same as input", "WARNING")
                        else:
                            try:
                                if settings["use_reply"]:
                                    send_message(channel_id, response_text, token, reply_to=reply_to_id,
                                                 delete_after=settings["delete_bot_reply"], delete_immediately=settings["delete_immediately"])
                                else:
                                    send_message(channel_id, response_text, token,
                                                 delete_after=settings["delete_bot_reply"], delete_immediately=settings["delete_immediately"])
                                last_message_time = time.time()
                                log_message(f"[{bot_username}] Sent: {response_text[:30]}...", "SUCCESS")
                            except requests.exceptions.RequestException as e:
                                if "429" in str(e):
                                    retry_after = int(e.response.headers.get('Retry-After', 10))
                                    rate_limit_until = time.time() + retry_after
                                    log_message(f"[{bot_username}] Rate limit: {retry_after}s", "WAIT")
                                    time.sleep(retry_after)
                                    try:
                                        if settings["use_reply"]:
                                            send_message(channel_id, response_text, token, reply_to=reply_to_id,
                                                         delete_after=settings["delete_bot_reply"], delete_immediately=settings["delete_immediately"])
                                        else:
                                            send_message(channel_id, response_text, token,
                                                         delete_after=settings["delete_bot_reply"], delete_immediately=settings["delete_immediately"])
                                        last_message_time = time.time()
                                        log_message(f"[{bot_username}] Sent: {response_text[:30]}...", "SUCCESS")
                                    except:
                                        log_message(f"[{bot_username}] Send failed", "ERROR")

                    # Small delay between direct replies
                    time.sleep(5)
                continue

            # Process regular messages with slow mode
            if messages:
                most_recent_message = messages[0]
                message_id = most_recent_message.get('id')
                author_id = most_recent_message.get('author', {}).get('id')
                message_type = most_recent_message.get('type', '')

                if author_id != bot_user_id and message_type != 8 and message_id not in processed_messages_by_token.get(token, set()):
                    user_message = most_recent_message.get('content', '').strip()
                    attachments = most_recent_message.get('attachments', [])
                    if attachments or not re.search(r'\w', user_message):
                        elapsed = time.time() - start_time
                        log_message(f"[Channel {channel_id}] [{elapsed:.1f}s] [{bot_username}] Message not processed (not pure text).", "WARNING")
                    else:
                        elapsed = time.time() - start_time
                        log_message(f"[Channel {channel_id}] [{elapsed:.1f}s] [{bot_username}] Received: {user_message}", "INFO")

                        # Apply slow mode delay if needed
                        if settings["use_slow_mode"]:
                            time_since_last = current_time - last_message_time
                            if time_since_last < slow_mode_delay:
                                wait_time = slow_mode_delay - time_since_last
                                elapsed = time.time() - start_time
                                log_message(f"[Channel {channel_id}] [{elapsed:.1f}s] [{bot_username}] Slow mode active, waiting {wait_time:.1f} seconds...", "WAIT")
                                time.sleep(wait_time)

                        prompt = user_message
                        reply_to_id = message_id
                        mark_message_processed_by_token(message_id, token)

                        # Process the message
                        context = build_context(messages, num_messages=30)
                        result = generate_reply(prompt, settings["prompt_language"], settings["use_google_ai"], context)

                        if result is None:
                            elapsed = time.time() - start_time
                            log_message(f"[Channel {channel_id}] [{elapsed:.1f}s] [{bot_username}] Invalid prompt language. Message skipped.", "WARNING")
                        elif result.lower() == "no reply":
                            elapsed = time.time() - start_time
                            log_message(f"[Channel {channel_id}] [{elapsed:.1f}s] [{bot_username}] Insufficient context; no reply generated.", "INFO")
                        else:
                            response_text = result if result else "sorry cannot reply"
                            if response_text.strip().lower() == prompt.strip().lower():
                                elapsed = time.time() - start_time
                                log_message(f"[Channel {channel_id}] [{elapsed:.1f}s] [{bot_username}] Reply same as received message. Not sending reply.", "WARNING")
                            else:
                                try:
                                    if settings["use_reply"]:
                                        send_message(channel_id, response_text, token, reply_to=reply_to_id,
                                                     delete_after=settings["delete_bot_reply"], delete_immediately=settings["delete_immediately"])
                                    else:
                                        send_message(channel_id, response_text, token,
                                                     delete_after=settings["delete_bot_reply"], delete_immediately=settings["delete_immediately"])
                                    last_message_time = time.time()
                                except requests.exceptions.RequestException as e:
                                    if "429" in str(e):
                                        retry_after = int(e.response.headers.get('Retry-After', 10))
                                        rate_limit_until = time.time() + retry_after
                                        elapsed = time.time() - start_time
                                        log_message(f"[Channel {channel_id}] [{elapsed:.1f}s] [{bot_username}] Rate limited, waiting {retry_after} seconds before retrying...", "WAIT")
                                        time.sleep(retry_after)
                                        try:
                                            if settings["use_reply"]:
                                                send_message(channel_id, response_text, token, reply_to=reply_to_id,
                                                             delete_after=settings["delete_bot_reply"], delete_immediately=settings["delete_immediately"])
                                            else:
                                                send_message(channel_id, response_text, token,
                                                             delete_after=settings["delete_bot_reply"], delete_immediately=settings["delete_immediately"])
                                            last_message_time = time.time()
                                        except:
                                            elapsed = time.time() - start_time
                                            log_message(f"[Channel {channel_id}] [{elapsed:.1f}s] [{bot_username}] Failed to send message after rate limit retry", "ERROR")

        except requests.exceptions.RequestException as e:
            elapsed = time.time() - start_time
            log_message(f"[Channel {channel_id}] [{elapsed:.1f}s] [{bot_username}] Request error: {e}", "ERROR")

        # Add token-specific delay before next iteration
        delay_interval = settings["delay_interval"] + (token_index * TOKEN_DELAY)
        elapsed = time.time() - start_time
        log_message(f"[Channel {channel_id}] [{elapsed:.1f}s] [{bot_username}] Waiting {delay_interval} seconds before next iteration...", "WAIT")
        time.sleep(delay_interval)

def send_message(channel_id, message_text, token, reply_to=None, delete_after=None, delete_immediately=False):
    headers = {'Authorization': token, 'Content-Type': 'application/json'}
    
    # Clean the message content
    message_text = message_text.strip()
    if len(message_text) > 2000:
        message_text = message_text[:1997] + "..."
    
    payload = {'content': message_text}
    if reply_to:
        payload["message_reference"] = {"message_id": reply_to}
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    
    max_retries = 3
    retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers)
            
            # Handle rate limits
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', retry_delay))
                log_message(f"[Channel {channel_id}] Rate limited, waiting {retry_after} seconds before retry {attempt + 1}/{max_retries}...", "WAIT")
                time.sleep(retry_after)
                continue
                
            # Handle bad requests
            if response.status_code == 400:
                log_message(f"[Channel {channel_id}] Bad request error. Cleaning message content...", "ERROR")
                # Further clean the message content
                message_text = re.sub(r'[^\x00-\x7F]+', '', message_text)  # Remove non-ASCII characters
                message_text = message_text.strip()
                if len(message_text) > 2000:
                    message_text = message_text[:1997] + "..."
                payload['content'] = message_text
                continue
                
            response.raise_for_status()
            
            if response.status_code in [200, 201]:
                data = response.json()
                message_id = data.get("id")
                log_message(f"[Channel {channel_id}]💬  Message sent: \"{message_text}\" (ID: {message_id})", "SUCCESS")
                # Add message ID to bot_message_ids immediately after sending
                bot_message_ids.add(message_id)
                if delete_after is not None:
                    if delete_immediately:
                        log_message(f"[Channel {channel_id}] Deleting message immediately without delay...", "WAIT")
                        threading.Thread(target=delete_message, args=(channel_id, message_id, token), daemon=True).start()
                    elif delete_after > 0:
                        log_message(f"[Channel {channel_id}] Message will be deleted in {delete_after} seconds...", "WAIT")
                        threading.Thread(target=delayed_delete, args=(channel_id, message_id, delete_after, token), daemon=True).start()
                return True
            else:
                log_message(f"[Channel {channel_id}] Failed to send message. Status: {response.status_code}", "ERROR")
                log_message(f"[Channel {channel_id}] API Response: {response.text}", "ERROR")
                return False
                
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                log_message(f"[Channel {channel_id}] Error sending message (attempt {attempt + 1}/{max_retries}): {e}", "ERROR")
                time.sleep(retry_delay)
            else:
                log_message(f"[Channel {channel_id}] Failed to send message after {max_retries} attempts: {e}", "ERROR")
                return False

def delayed_delete(channel_id, message_id, delay, token):
    time.sleep(delay)
    delete_message(channel_id, message_id, token)

def delete_message(channel_id, message_id, token):
    headers = {'Authorization': token, 'Content-Type': 'application/json'}
    url = f'https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}'
    try:
        response = requests.delete(url, headers=headers)
        if response.status_code == 204:
            log_message(f"[Channel {channel_id}] Message with ID {message_id} successfully deleted.", "SUCCESS")
        else:
            log_message(f"[Channel {channel_id}] Failed to delete message. Status: {response.status_code}", "ERROR")
            log_message(f"[Channel {channel_id}] API Response: {response.text}", "ERROR")
    except requests.exceptions.RequestException as e:
        log_message(f"[Channel {channel_id}] Error deleting message: {e}", "ERROR")

def get_slow_mode_delay(channel_id, token):
    headers = {'Authorization': token, 'Accept': 'application/json'}
    url = f"https://discord.com/api/v9/channels/{channel_id}"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        slow_mode_delay = data.get("rate_limit_per_user", 0)
        log_message(f"[Channel {channel_id}] Slow mode delay: {slow_mode_delay} seconds", "INFO")
        return slow_mode_delay
    except requests.exceptions.RequestException as e:
        log_message(f"[Channel {channel_id}] Failed to get slow mode info: {e}", "ERROR")
        return 5

def print_settings_header(channel_id, channel_name, server_name):
    max_width = max(
        len(channel_id) + 4,
        len(channel_name) + 4,
        len(server_name) + 4,
        len("Channel Settings Configuration") + 4
    )
    top_border = f"{Fore.MAGENTA}╔{'═' * max_width}╗{Style.RESET_ALL}"
    bottom_border = f"{Fore.MAGENTA}╚{'═' * max_width}╝{Style.RESET_ALL}"
    side_border = f"{Fore.MAGENTA}║{Style.RESET_ALL}"
    title = f"{Fore.CYAN}🌟 Channel Settings Configuration 🌟{Style.RESET_ALL}"
    title_padding = ' ' * ((max_width - len(title)) // 2)
    server_info = f"{Fore.GREEN}🌐 Server:{Style.RESET_ALL} {Fore.YELLOW}{server_name}{Style.RESET_ALL}"
    channel_details = f"{Fore.GREEN}📝 Channel:{Style.RESET_ALL} {Fore.YELLOW}{channel_name}{Style.RESET_ALL} ({Fore.BLUE}{channel_id}{Style.RESET_ALL})"
    server_padding = ' ' * (max_width - len(server_info) - 2)
    channel_padding = ' ' * (max_width - len(channel_details) - 2)
    print(f"\n{top_border}")
    print(f"{side_border}{title_padding}{title}{title_padding}{side_border}")
    print(f"{side_border}{' ' * max_width}{side_border}")
    print(f"{side_border} {server_info}{server_padding}{side_border}")
    print(f"{side_border} {channel_details}{channel_padding}{side_border}")
    print(f"{bottom_border}\n")

def print_section_header(title):
    icons = {
        "AI and Language Settings": "🤖",
        "Timing Settings": "⏱️",
        "Message Settings": "💬",
        "Moderation Settings": "⚙️"
    }
    icon = icons.get(title, "⚙️")
    header = f"{Fore.CYAN}{icon} {title} {icon}{Style.RESET_ALL}"
    line = f"{Fore.MAGENTA}{'─' * 3} {header} {'─' * (76 - len(header))}{Style.RESET_ALL}"
    print(f"\n{line}")

def get_yes_no_input(prompt, default='n'):
    while True:
        choice = input(f"{Fore.GREEN}❓ {prompt} {Fore.YELLOW}(y/n) [{default}]: {Style.RESET_ALL}").strip().lower() or default
        if choice in ['y', 'n']:
            return choice == 'y'
        print(f"{Fore.RED}❌ Invalid input. Please enter 'y' or 'n'.{Style.RESET_ALL}")

def get_language_input(prompt, default='en'):
    while True:
        choice = input(f"{Fore.GREEN}🌐 {prompt} {Fore.YELLOW}(en/hi) [{default}]: {Style.RESET_ALL}").strip().lower() or default
        if choice in ['en', 'hi']:
            return choice
        print(f"{Fore.RED}❌ Invalid input. Please enter 'en' or 'hi'.{Style.RESET_ALL}")

def get_number_input(prompt, min_value=0, default=None):
    while True:
        try:
            default_str = f" [{default}]" if default is not None else ""
            value = input(f"{Fore.GREEN}🔢 {prompt}{Fore.YELLOW}{default_str}: {Style.RESET_ALL}").strip()
            if not value and default is not None:
                return default
            value = int(value)
            if value >= min_value:
                return value
            print(f"{Fore.RED}❌ Please enter a number greater than or equal to {min_value}.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}❌ Invalid input. Please enter a valid number.{Style.RESET_ALL}")

def print_settings_summary(settings):
    max_width = 60  # Reduced width for more precise control
    top_border = f"{Fore.MAGENTA}╔{'═' * max_width}╗{Style.RESET_ALL}"
    bottom_border = f"{Fore.MAGENTA}╚{'═' * max_width}╝{Style.RESET_ALL}"
    side_border = f"{Fore.MAGENTA}║{Style.RESET_ALL}"

    def get_visual_length(s):
        # Remove ANSI escape codes and count Unicode chars properly
        s = re.sub(r'\x1b\[[0-9;]*m', '', s)
        # Count emoji and other wide characters as 2 spaces
        length = 0
        for char in s:
            if ord(char) > 0xFFFF or char in '🤖⏱️💬🛡️✨✅❌':
                length += 2
            else:
                length += 1
        return length

    def print_line(content, indent=0):
        visual_length = get_visual_length(content)
        padding = max_width - visual_length - indent
        print(f"{side_border}{' ' * indent}{content}{' ' * padding}{side_border}")

    print(f"\n{top_border}")
    
    # Title
    title = f"{Fore.CYAN}✨ Settings Summary ✨{Style.RESET_ALL}"
    title_padding = (max_width - get_visual_length("✨ Settings Summary ✨")) // 2
    print_line(title, title_padding)
    print_line("", 0)  # Empty line after title

    # AI and Language Settings
    print_line(f"{Fore.YELLOW}🤖 AI and Language:{Style.RESET_ALL}", 1)
    print_line(f"{Fore.GREEN}Use Google Gemini AI: {Fore.CYAN}{'✅ Yes' if settings['use_google_ai'] else '❌ No'}{Style.RESET_ALL}", 3)
    print_line(f"{Fore.GREEN}Language: {Fore.CYAN}{settings['prompt_language'].upper()}{Style.RESET_ALL}", 3)
    print_line("", 0)  # Empty line between sections

    # Timing Settings
    print_line(f"{Fore.YELLOW}⏱️ Timing Settings:{Style.RESET_ALL}", 1)
    if settings['use_google_ai']:
        print_line(f"{Fore.GREEN}Message Read Delay: {Fore.CYAN}{settings['read_delay']} seconds{Style.RESET_ALL}", 3)
    print_line(f"{Fore.GREEN}Reply Interval: {Fore.CYAN}{settings['delay_interval']} seconds{Style.RESET_ALL}", 3)
    print_line(f"{Fore.GREEN}Use Slow Mode: {Fore.CYAN}{'✅ Yes' if settings['use_slow_mode'] else '❌ No'}{Style.RESET_ALL}", 3)
    print_line("", 0)  # Empty line between sections

    # Message Settings
    print_line(f"{Fore.YELLOW}💬 Message Settings:{Style.RESET_ALL}", 1)
    print_line(f"{Fore.GREEN}Send as Reply: {Fore.CYAN}{'✅ Yes' if settings['use_reply'] else '❌ No'}{Style.RESET_ALL}", 3)
    if settings['delete_bot_reply'] is not None:
        delete_str = ("Immediately" if settings['delete_immediately'] 
                      else (f"In {settings['delete_bot_reply']} seconds" if settings['delete_bot_reply'] and settings['delete_bot_reply'] > 0 else "No"))
        print_line(f"{Fore.GREEN}Delete Messages: {Fore.CYAN}{delete_str}{Style.RESET_ALL}", 3)
    else:
        print_line(f"{Fore.GREEN}Delete Messages: {Fore.CYAN}❌ No{Style.RESET_ALL}", 3)
    print_line("", 0)  # Empty line between sections

    # Moderation Settings
    print_line(f"{Fore.YELLOW}🛡️ Moderation Settings:{Style.RESET_ALL}", 1)
    print_line(f"{Fore.GREEN}Auto Moderation: {Fore.CYAN}✅ Enabled{Style.RESET_ALL}", 3)
    print_line(f"{Fore.GREEN}Cooldown Mode: {Fore.CYAN}Until 50 regular messages{Style.RESET_ALL}", 3)
    print_line(f"{Fore.GREEN}Role Detection: {Fore.CYAN}✅ Automatic{Style.RESET_ALL}", 3)

    print(bottom_border)

def get_server_settings(channel_id, channel_name, server_name="Unknown Server"):
    print_settings_header(channel_id, channel_name, server_name)
    print_section_header("AI and Language Settings")
    use_google_ai = get_yes_no_input("Use Google Gemini AI?", default='y')
    prompt_language = get_language_input("Choose prompt language", 'en')
    print_section_header("Timing Settings")
    if use_google_ai:
        read_delay = get_number_input("Enter message read delay (seconds)", min_value=0, default=5)
        delay_interval = get_number_input("Enter interval (seconds) for each auto reply iteration", min_value=1, default=10)
        use_slow_mode = get_yes_no_input("Use slow mode?", default='y')
    else:
        read_delay = 0
        delay_interval = get_number_input("Enter delay (seconds) for sending messages from file", min_value=1, default=10)
        use_slow_mode = True
    print_section_header("Message Settings")
    use_reply = get_yes_no_input("Send message as reply?", default='y')
    delete_reply = get_yes_no_input("Delete bot reply after some time?", default='n')
    if delete_reply:
        delete_bot_reply = get_number_input("After how many seconds to delete reply? (0 for immediate)", min_value=0)
        delete_immediately = delete_bot_reply == 0
    else:
        delete_bot_reply = None
        delete_immediately = False
    
    print_section_header("Moderation Settings")
    print(f"{Fore.CYAN}ℹ️  Moderation is automatically handled:{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✓  Bot enters cooldown when moderator sends stop command{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✓  Cooldown continues until 50 regular messages are received{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✓  Automatic role-based moderation detection{Style.RESET_ALL}")
    
    settings = {
        "prompt_language": prompt_language,
        "use_google_ai": use_google_ai,
        "enable_read_message": use_google_ai,
        "read_delay": read_delay,
        "delay_interval": delay_interval,
        "use_slow_mode": use_slow_mode,
        "use_reply": use_reply,
        "delete_bot_reply": delete_bot_reply,
        "delete_immediately": delete_immediately
    }
    print_settings_summary(settings)
    return settings

if __name__ == "__main__":
    try:
        banner = """
          ('-.      .-')    ('-. .-.             
          ( OO ).-. ( OO ). ( OO )  /             
          / . --. /(_)---\_),--. ,--. ,--. ,--.   
          | \-.  \ /    _ | |  | |  | |  | |  |   
        .-'-'  |  |\  :` `. |   .|  | |  | | .-') 
         \| |_.'  | '..`''.)|       | |  |_|( OO )
          |  .-.  |.-._)   \|  .-.  | |  | | `-' /
          |  | |  |\       /|  | |  |('  '-'(_.-' 
          `--' `--' `-----' `--' `--'  `-----' 
        """
        print(f"{Fore.CYAN}{banner}{Style.RESET_ALL}")
        
        logger.info("Starting Discord Bot...")
        logger.info(f"Loaded {len(discord_tokens)} Discord tokens")
        logger.info(f"Loaded {len(google_api_keys)} Google API keys")

        bot_accounts = {}
        for token in discord_tokens:
            username, discriminator, bot_id = get_bot_info(token)
            bot_accounts[token] = {"username": username, "discriminator": discriminator, "bot_id": bot_id}
            log_message(f"Bot Account: {username}#{discriminator} (ID: {bot_id})", "SUCCESS")

        logger.info(f"Processing {len(channel_ids)} channels")

        channel_infos = {}
        for channel_id in channel_ids:
            server_name, channel_name = get_channel_info(channel_id, discord_tokens[0])
            channel_infos[channel_id] = {"server_name": server_name, "channel_name": channel_name}
            log_message(f"Connected to server: {server_name} | Channel Name: {channel_name}", "SUCCESS", channel_id)

        server_settings = {}
        for channel_id in channel_ids:
            info = channel_infos.get(channel_id, {})
            channel_name = info.get("channel_name", "Unknown Channel")
            server_name = info.get("server_name", "Unknown Server")
            server_settings[channel_id] = get_server_settings(channel_id, channel_name, server_name)

        # Start threads for all tokens per channel
        for channel_id in channel_ids:
            # Use all available tokens for each channel
            for token_index in range(len(discord_tokens)):
                token = discord_tokens[token_index]
                bot_info = bot_accounts.get(token, {"username": "Unknown", "discriminator": "", "bot_id": "Unknown"})
                
                thread = threading.Thread(
                    target=auto_reply,
                    args=(channel_id, server_settings[channel_id], token)
                )
                thread.daemon = True
                thread.start()
                log_message(f"Bot active: {bot_info['username']}#{bot_info['discriminator']} (Token: {token[:4]}{'...' if len(token) > 4 else token})", "SUCCESS", channel_id)

        logger.info(f"Bot is running on multiple servers with {len(discord_tokens)} tokens per channel... Press CTRL+C to stop.")
        while True:
            time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Bot shutdown initiated by user...")
    except Exception as e:
        logger.critical(f"Critical error occurred: {str(e)}", exc_info=True)
    finally:
        logger.info("Bot shutdown complete.")

