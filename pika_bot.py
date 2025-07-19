import discord
import random
import asyncio
import json 
import os
import traceback
import datetime
import time
import string
from collections import deque
from discord.ext import commands, tasks
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
from collections import defaultdict, deque
from typing import Dict, List
import re

# ─── Load valid English words ────────────────────────────────────
with open("words_alpha.txt", encoding="utf-8") as f:
    valid_words = set(line.strip().lower() for line in f if line.strip())

# ─── Configuration ─────────────────────────────────────────────────
# Session-only conversation history (not saved to disk)
conversation_history = {}
CONVERSATION_LIMIT = 50  # Keep last 50 messages per user in memory

DISK_PATH = os.getenv("PIKA_DISK_MOUNT_PATH", "/var/data")
PIKA_FILE = os.path.join(DISK_PATH, "pikapoints.json")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))
assert os.path.isdir(DISK_PATH), f"Disk path {DISK_PATH} not found!"

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ─── Logging System ─────────────────────────────────────────────────

class DiscordLogger:
    def __init__(self, bot):
        self.bot = bot
        self.log_channel = None
        
    async def initialize(self):
        """Initialize the log channel after bot is ready"""
        if LOG_CHANNEL_ID:
            try:
                self.log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
                if not self.log_channel:
                    print(f"Warning: Could not find log channel with ID {LOG_CHANNEL_ID}")
            except Exception as e:
                print(f"Error initializing log channel: {e}")
    
    async def log_command_usage(self, ctx, command_name, success=True, extra_info=""):
        """Log command usage with context"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
        embed = discord.Embed(
            title=f"Command: {command_name}",
            color=0x00ff00 if success else 0xff0000,
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(name="User", value=f"{ctx.author.mention} ({ctx.author.id})", inline=True)
        embed.add_field(name="Guild", value=f"{ctx.guild.name} ({ctx.guild.id})", inline=True)
        embed.add_field(name="Channel", value=f"#{ctx.channel.name} ({ctx.channel.id})", inline=True)
        
        if extra_info:
            embed.add_field(name="Details", value=extra_info[:1024], inline=False)
            
        await self._send_log(embed)
    
    async def log_error(self, error, context="General Error", extra_details=""):
        """Log errors with full traceback"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        embed = discord.Embed(
            title="🚨 ERROR OCCURRED",
            color=0xff0000,
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(name="Context", value=context, inline=True)
        embed.add_field(name="Error Type", value=type(error).__name__, inline=True)
        embed.add_field(name="Error Message", value=str(error)[:1024], inline=False)
        
        if extra_details:
            embed.add_field(name="Extra Details", value=extra_details[:1024], inline=False)
        
        # Add traceback as a separate field
        tb = traceback.format_exc()
        if len(tb) > 1024:
            tb = tb[-1024:]  # Keep last 1024 chars of traceback
        embed.add_field(name="Traceback", value=f"```python\n{tb}\n```", inline=False)
        
        await self._send_log(embed)
    
    async def log_ai_usage(self, user_id, guild_id, prompt_length, response_length, success=True):
        """Log AI command usage"""
        embed = discord.Embed(
            title="🤖 AI Command Usage",
            color=0x9932cc,
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(name="User ID", value=str(user_id), inline=True)
        embed.add_field(name="Guild ID", value=str(guild_id), inline=True)
        embed.add_field(name="Prompt Length", value=f"{prompt_length} chars", inline=True)
        embed.add_field(name="Response Length", value=f"{response_length} chars", inline=True)
        embed.add_field(name="Success", value="✅" if success else "❌", inline=True)
        
        await self._send_log(embed)
    
    async def log_bot_event(self, event_type, message):
        """Log general bot events"""
        embed = discord.Embed(
            title=f"🔔 Bot Event: {event_type}",
            color=0x808080,
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(name="Message", value=message[:1024], inline=False)
        
        await self._send_log(embed)
    
    async def log_game_result(self, game_type, winner_id, guild_id, extra_info=""):
        """Log game results"""
        embed = discord.Embed(
            title=f"🎮 Game Result: {game_type}",
            color=0x00ff00,
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(name="Winner ID", value=str(winner_id), inline=True)
        embed.add_field(name="Guild ID", value=str(guild_id), inline=True)
        if extra_info:
            embed.add_field(name="Details", value=extra_info[:1024], inline=False)
        
        await self._send_log(embed)
    
    async def log_points_award(self, user_id, guild_id, points, reason, total_points):
        """Log points awards"""
        embed = discord.Embed(
            title="💰 Points Awarded",
            color=0xffd700,
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(name="User ID", value=str(user_id), inline=True)
        embed.add_field(name="Guild ID", value=str(guild_id), inline=True)
        embed.add_field(name="Points Awarded", value=str(points), inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.add_field(name="Total Points", value=str(total_points), inline=True)
        
        await self._send_log(embed)
    
    async def _send_log(self, embed):
        """Internal method to send log to Discord channel"""
        if self.log_channel:
            try:
                await self.log_channel.send(embed=embed)
            except Exception as e:
                print(f"Failed to send log to Discord: {e}")
        else:
            print("Log channel not available - printing to console:")
            print(f"Title: {embed.title}")
            for field in embed.fields:
                print(f"{field.name}: {field.value}")

# Initialize logger
logger = DiscordLogger(bot)

# ─── Hot Take System Variables ─────────────────────────────────────────────────
HOT_TAKE_CHANNEL_ID = 1392813388286918696
HOT_TAKE_FILE = os.path.join(os.path.dirname(__file__), "hot_takes.txt")
HOT_TAKE_STATE_FILE = os.path.join(DISK_PATH, "hot_take_state.json")
HOT_TAKE_INTERVAL = 60 * 60 * 12  # 12 hours in seconds

# Load hot takes
with open(HOT_TAKE_FILE, encoding="utf-8") as f:
    hot_takes = [line.strip() for line in f if line.strip()]

def load_hot_take_state():
    if not os.path.exists(HOT_TAKE_STATE_FILE):
        return {"last_sent": 0, "last_index": -1, "order": list(range(len(hot_takes)))}
    with open(HOT_TAKE_STATE_FILE, "r") as f:
        return json.load(f)

def save_hot_take_state(state):
    with open(HOT_TAKE_STATE_FILE, "w") as f:
        json.dump(state, f)
        f.flush()
        os.fsync(f.fileno())

hot_take_state = load_hot_take_state()

# Shuffle order if needed
if not hot_take_state.get("order") or len(hot_take_state["order"]) != len(hot_takes):
    hot_take_state["order"] = list(range(len(hot_takes)))
    random.shuffle(hot_take_state["order"])
    save_hot_take_state(hot_take_state)

# ─── Bot Events ─────────────────────────────────────────────────

@bot.event
async def on_ready():
    """Bot startup event"""
    await logger.initialize()
    await logger.log_bot_event("Bot Started", f"Pikabug is online! Logged in as {bot.user}")
    print(f'{bot.user} has connected to Discord!')
    print(f'Disk path: {DISK_PATH}')
    print(f'Disk path exists: {os.path.exists(DISK_PATH)}')
    if os.path.exists(DISK_PATH):
        print(f'Files in disk: {os.listdir(DISK_PATH)}')
    
    # Start the hot take task if not already running
    if not send_hot_take.is_running():
        send_hot_take.start()

@bot.event
async def on_command_error(ctx, error):
    """Global error handler"""
    await logger.log_error(
        error, 
        f"Command Error in {ctx.command.name if ctx.command else 'Unknown Command'}", 
        f"User: {ctx.author.id}, Guild: {ctx.guild.id if ctx.guild else 'DM'}"
    )
    
    # Send user-friendly error message
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found. Use `!pikahelp` to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument. Check the command usage with `!pikahelp`.")
    else:
        await ctx.send("❌ An error occurred while processing your command.")

# ─── PikaPoints Data ─────────────────────────────────────────────────

# PikaPoints reward values
PROMPT_POINTS = 15
VENT_POINTS = 10
PREFIXGAME_POINTS = 5
UNSCRAMBLE_POINTS = 5
WORKSHOP_POINTS = 20
WORDSEARCH_POINTS = 5

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_pikapoints():
    if not os.path.exists(PIKA_FILE):
        with open(PIKA_FILE, "w") as f:
            json.dump({}, f)
    with open(PIKA_FILE, "r") as f:
        return json.load(f)

def save_pikapoints(data: dict):
    with open(PIKA_FILE, "w") as f:
        json.dump(data, f)
        f.flush()
        os.fsync(f.fileno())

pika_data = load_pikapoints()

WORKSHOP_CHANNEL_ID = 1392093043800412160

def get_user_record(guild_id: str, user_id: str):
    guild = pika_data.setdefault(guild_id, {})
    return guild.setdefault(user_id, {
        "points": 0,
        "prompt_submissions": 0,
        "vent_submissions": 0,
        "workshop_submissions": 0,
        "prefixgame_submissions": 0,
        "unscramble_submissions": 0,
        "wordsearch_submissions": 0,
    })

# Add event listener for awarding workshop points
def is_workshop_channel(channel):
    return channel.id == WORKSHOP_CHANNEL_ID

# ─── AI Chat Command ─────────────────────────────────────────────────

@bot.command(name="chat")
async def chat(ctx, *, prompt):
    thinking_msg = await ctx.send("Thinking...")
    user_key = f"{ctx.guild.id}-{ctx.author.id}"
    
    try:
        # Ensure memory for the user exists (session-only)
        if user_key not in conversation_history:
            conversation_history[user_key] = deque(maxlen=CONVERSATION_LIMIT)

        # Build messages for OpenAI in proper order
        messages = []
        
        # 1. ALWAYS start with system prompt (personality) - this must be first
        messages.append({
            "role": "system", 
            "content": """You are Pikabug, a nonchalant, humorously edgy Discord companion.

CRITICAL PERSONALITY TRAITS (ALWAYS FOLLOW THESE):
- Always use edgy or snarky, unpredictable and controversial humor and sarcasm in general discussion
- Only use empathetic, supportive language when user needs emotional support or when user seems upset 
- Never use outdated slang, phrases, or millennial jokes 
- Never sound robotic or repetitive during any discussion. Keep responses unexpected and rare
- Suggest concrete, meaningful coping methods rather than generic advice when providing emotional support
- Have strong opinions and don't be wishy-washy
- When asked to pick between two options, ONLY respond with chosen option
- Be on the side of the user and don't play devil's advocate

COMMUNICATION STYLE (ALWAYS FOLLOW THESE):
- Only use lengthy, meaningful responses for emotional support 
- Only use nonchalant and unpredictable or edgy responses for general discussion
- Always implement controversial humor in general discussion
- Never resemble a bot in responses and speak human-like

REMEMBER: You are edgy, blunt, and nonchalant unless giving support. NEVER ignore these personality instructions."""
        })
        
        # 2. Add conversation history (if any exists)
        if conversation_history[user_key]:
            messages.extend(list(conversation_history[user_key]))
        
        # 3. Add current user message
        messages.append({"role": "user", "content": prompt})

        # Make OpenAI API call
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=1000,
            temperature=1.0
        )

        reply = response.choices[0].message.content

        # Save to session memory only (not to disk)
        conversation_history[user_key].append({"role": "user", "content": prompt})
        conversation_history[user_key].append({"role": "assistant", "content": reply})

        await thinking_msg.edit(content=reply)
        
        # Log successful AI usage
        await logger.log_ai_usage(
            ctx.author.id, 
            ctx.guild.id, 
            len(prompt), 
            len(reply), 
            success=True
        )
        await logger.log_command_usage(ctx, "chat", success=True, 
                                     extra_info=f"Prompt: {prompt[:100]}... | History: {len(conversation_history[user_key])} messages")

    except Exception as e:
        error_msg = f"⚠️ Error occurred: {str(e)}"
        await thinking_msg.edit(content=error_msg)
        await logger.log_error(e, "AI Command Error", f"User: {ctx.author.id}, Prompt: {prompt[:100]}...")
        await logger.log_ai_usage(ctx.author.id, ctx.guild.id, len(prompt), 0, success=False)

# ─── Word Games ─────────────────────────────────────────────────

# ─── Build prefix→words map from valid_words ─────────────────────
prefix_map: Dict[str, List[str]] = defaultdict(list)
for w in valid_words:
    # only consider words at least 3 letters long
    if len(w) >= 3:
        p = w[:3]               # extract the 3‐letter prefix
        prefix_map[p].append(w)

# ─── Filter to "common" prefixes ────────────────────────────────
MIN_WORDS_PER_PREFIX = 5
common_prefixes: List[str] = [
    p for p, lst in prefix_map.items()
    if len(lst) >= MIN_WORDS_PER_PREFIX
]

@bot.command(name="prefixgame")
async def prefixgame(ctx):
    try:
        # Pick and announce a prefix
        weights = [len(prefix_map[p]) for p in common_prefixes]
        current_prefix = random.choices(common_prefixes, weights=weights, k=1)[0]
        await ctx.send(f"🧠 New round! Submit the **longest** word starting with: `{current_prefix}`")

        # Collect submissions
        submissions: Dict[discord.Member, str] = {}

        while True:
            try:
                msg = await bot.wait_for("message", timeout=12.0, check=lambda m: 
                    m.channel == ctx.channel and
                    not m.author.bot and
                    m.content.lower().strip().startswith(current_prefix) and
                    len(m.content.strip()) > len(current_prefix)
                )
                word = msg.content.strip().lower()
                if word not in valid_words:
                    await ctx.send(f"{msg.author.mention} ❌ '{word}' isn't a valid English word.")
                    continue
                prev = submissions.get(msg.author)
                if prev is None or len(word) > len(prev):
                    submissions[msg.author] = word
            except asyncio.TimeoutError:
                break

        if not submissions:
            await ctx.send("⏲ Time's up! No valid entries were submitted.")
            await logger.log_command_usage(
                ctx,
                "prefixgame",
                success=True,
                extra_info="No submissions"
            )
            return

        # Determine winner and award points
        winner, winning_word = max(submissions.items(), key=lambda kv: len(kv[1]))
        guild_id = str(ctx.guild.id)
        user_id = str(winner.id)
        record = get_user_record(guild_id, user_id)
        record["points"] += PREFIXGAME_POINTS
        record["prefixgame_submissions"] += 1
        save_pikapoints(pika_data)

        # Send results
        await ctx.send(
            f"🏆 **{winner.display_name}** wins with **{winning_word}** ({len(winning_word)} letters)!\n"
            f"You earned **{PREFIXGAME_POINTS}** PikaPoints!\n"
            f"• Total Points: **{record['points']}**\n"
            f"• Prefix-game entries: **{record['prefixgame_submissions']}**"
        )

        await logger.log_command_usage(ctx, "prefixgame", success=True, extra_info=f"Winner: {winner.display_name}")

    except Exception as e:
        await logger.log_error(e, "Prefix Game Error")
        await logger.log_command_usage(ctx, "prefixgame", success=False)

# ─── Unscramble Game ─────────────────────────────────────────────────

# Load English word list
with open("common_words.txt") as f:
    english_words = [word.strip() for word in f if 5 <= len(word.strip()) <= 7]

# Store current word challenge
current_word = None
scrambled_word = None
revealed_indexes = set()
hint_count = 0

@bot.command(name='unscramble')
async def unscramble(ctx):
    try:
        global current_word, scrambled_word, revealed_indexes, hint_count
        current_word = random.choice(english_words)
        scrambled_word = ''.join(random.sample(current_word, len(current_word)))

        # Reset hint tracking
        revealed_indexes = set([0, len(current_word) - 1])
        hint_count = 0

        await ctx.send(f"🧠 Unscramble this word: **{scrambled_word}**")
        await logger.log_command_usage(ctx, "unscramble", success=True, extra_info=f"Word: {current_word}")
        
    except Exception as e:
        await logger.log_error(e, "Unscramble Start Error")
        await logger.log_command_usage(ctx, "unscramble", success=False)

@bot.command(name='guess')
async def guess(ctx, user_guess: str):
    try:
        global current_word
        if current_word is None:
            await ctx.send("❗ No game running. Start one with `!unscramble`.")
            await logger.log_command_usage(ctx, "guess", success=False, extra_info="No active game")
            return

        if user_guess.lower() == current_word.lower():
            # Award points
            guild_id = str(ctx.guild.id)
            user_id  = str(ctx.author.id)
            record   = get_user_record(guild_id, user_id)
            record['points'] += UNSCRAMBLE_POINTS
            record['unscramble_submissions'] += 1
            save_pikapoints(pika_data)

            await ctx.send(
                f"✅ Correct! You earned **{UNSCRAMBLE_POINTS}** PikaPoints.\n"
                f"• **Total Points:** {record['points']}\n"
                f"• **Unscramble Submissions:** {record['unscramble_submissions']}"
            )

            # Log success
            await logger.log_command_usage(ctx, "guess", success=True, extra_info=f"Correct guess: {user_guess}")
            
            current_word = None
        else:
            await ctx.send("❌ Nope, try again.")
            await logger.log_command_usage(ctx, "guess", success=True, extra_info=f"Incorrect guess: {user_guess}")
            
    except Exception as e:
        await logger.log_error(e, "Guess Command Error")
        await logger.log_command_usage(ctx, "guess", success=False)

@bot.command(name='hint')
async def hint(ctx):
    try:
        global current_word, revealed_indexes, hint_count

        if current_word is None:
            await ctx.send("❗ No game is active. Start with `!unscramble`.")
            await logger.log_command_usage(ctx, "hint", success=False, extra_info="No active game")
            return

        hint_count += 1

        if hint_count > 1:
            possible_indexes = [
                i for i in range(1, len(current_word) - 1)
                if i not in revealed_indexes
            ]
            if possible_indexes:
                new_index = random.choice(possible_indexes)
                revealed_indexes.add(new_index)

        display = ""
        for i, char in enumerate(current_word):
            if i in revealed_indexes:
                display += char + " "
            else:
                display += "_ "

        await ctx.send(f"💡 Hint: {display.strip()}")
        await logger.log_command_usage(ctx, "hint", success=True, extra_info=f"Hint #{hint_count}")
        
    except Exception as e:
        await logger.log_error(e, "Hint Command Error")
        await logger.log_command_usage(ctx, "hint", success=False)

@bot.command(name='reveal')
async def reveal(ctx):
    try:
        global current_word
        if current_word is None:
            await ctx.send("❗ No word to reveal. Start a new game with `!unscramble`.")
            await logger.log_command_usage(ctx, "reveal", success=False, extra_info="No active game")
        else:
            await ctx.send(f"🕵️ The correct word was: **{current_word}**")
            await logger.log_command_usage(ctx, "reveal", success=True, extra_info=f"Revealed word: {current_word}")
            current_word = None
            
    except Exception as e:
        await logger.log_error(e, "Reveal Command Error")
        await logger.log_command_usage(ctx, "reveal", success=False)

# --- Word Search Game (5x5, 5-letter words, hidden words not shown) ---

def load_wordsearch_words():
    with open("common_words.txt") as f:
        words = [w.strip().lower() for w in f if w.strip()]
        # Separate 4-letter, 5-letter, and 6-letter words
        four_letter_words = [w for w in words if len(w) == 4]
        five_letter_words = [w for w in words if len(w) == 5]
        six_letter_words = [w for w in words if len(w) == 6]
        return four_letter_words, five_letter_words, six_letter_words

four_letter_words, five_letter_words, six_letter_words = load_wordsearch_words()

# Track active word search games per user
active_wordsearch_games = {}
wordsearch_word_history = deque(maxlen=50)  # Track last 50 words used

class WordSearchGame:
    def __init__(self, four_letter_word, five_letter_word, six_letter_word):
        self.grid_size = 8
        self.grid = [['' for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.words = [four_letter_word.lower(), five_letter_word.lower(), six_letter_word.lower()]
        self.found_words = set()
        self.word_positions = {}  # Track where each word is placed
        self.used_positions = set()  # Track all used positions to prevent overlap
        self._create_grid()
    
    def _create_grid(self):
        # Fill grid with random letters first
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                self.grid[i][j] = random.choice(string.ascii_lowercase)
        
        # Directions: (row_delta, col_delta)
        directions = [
            (0, 1),   # horizontal right
            (0, -1),  # horizontal left
            (1, 0),   # vertical down
            (-1, 0),  # vertical up
            (1, 1),   # diagonal down-right
            (-1, -1), # diagonal up-left
            (1, -1),  # diagonal down-left
            (-1, 1),  # diagonal up-right
        ]
        
        # Place each word
        for word in self.words:
            placed = False
            attempts = 0
            
            # Try random placement first
            while not placed and attempts < 200:
                attempts += 1
                direction = random.choice(directions)
                start_row = random.randint(0, self.grid_size - 1)
                start_col = random.randint(0, self.grid_size - 1)
                
                if self._can_place_word(word, start_row, start_col, direction):
                    self._place_word(word, start_row, start_col, direction)
                    placed = True
            
            # If random placement failed, try systematic placement
            if not placed:
                for direction in directions:
                    for start_row in range(self.grid_size):
                        for start_col in range(self.grid_size):
                            if self._can_place_word(word, start_row, start_col, direction):
                                self._place_word(word, start_row, start_col, direction)
                                placed = True
                                break
                        if placed:
                            break
                    if placed:
                        break
            
            # If still not placed, force place it (this shouldn't happen with 4-6 letter words in 8x8 grid)
            if not placed:
                print(f"Warning: Could not place word '{word}' in grid")
    
    def _can_place_word(self, word, start_row, start_col, direction):
        row_delta, col_delta = direction
        positions_to_check = []
        
        # Check if all positions are within bounds and not already used
        for i, letter in enumerate(word):
            row = start_row + i * row_delta
            col = start_col + i * col_delta
            
            # Check boundaries
            if row < 0 or row >= self.grid_size or col < 0 or col >= self.grid_size:
                return False
            
            # Check if position is already used
            if (row, col) in self.used_positions:
                return False
            
            positions_to_check.append((row, col))
        
        return True
    
    def _place_word(self, word, start_row, start_col, direction):
        row_delta, col_delta = direction
        positions = []
        for i, letter in enumerate(word):
            row = start_row + i * row_delta
            col = start_col + i * col_delta
            self.grid[row][col] = letter
            positions.append((row, col))
            self.used_positions.add((row, col))  # Mark position as used
        self.word_positions[word] = positions
    
    def display_grid(self):
        grid_str = "```\n"
        for row in self.grid:
            grid_str += " ".join(letter.upper() for letter in row) + "\n"
        grid_str += "```"
        return grid_str
    
    def check_word(self, word):
        word = word.lower()
        if word in self.words and word not in self.found_words:
            self.found_words.add(word)
            return True
        return False
    
    def is_complete(self):
        return len(self.found_words) == len(self.words)

@bot.command(name='wordsearch')
async def wordsearch(ctx):
    try:
        # Filter for available words
        available_four_letter = [w for w in four_letter_words if w not in wordsearch_word_history]
        available_five_letter = [w for w in five_letter_words if w not in wordsearch_word_history]
        available_six_letter = [w for w in six_letter_words if w not in wordsearch_word_history]
        
        # If we don't have enough words, use all available
        if len(available_four_letter) < 1:
            available_four_letter = four_letter_words
        if len(available_five_letter) < 1:
            available_five_letter = five_letter_words
        if len(available_six_letter) < 1:
            available_six_letter = six_letter_words
        
        # Select one 4-letter word, one 5-letter word, and one 6-letter word
        selected_four_letter = random.choice(available_four_letter)
        selected_five_letter = random.choice(available_five_letter)
        selected_six_letter = random.choice(available_six_letter)
        
        wordsearch_word_history.extend([selected_four_letter, selected_five_letter, selected_six_letter])
        
        # Create game
        game = WordSearchGame(selected_four_letter, selected_five_letter, selected_six_letter)
        active_wordsearch_games[ctx.author.id] = game
        
        await ctx.send(
            f"🔍 **Word Search Game Started!**\n"
            f"Find **3 hidden words** in this 8x8 grid:\n"
            f"• One 4-letter word\n"
            f"• One 5-letter word\n"
            f"• One 6-letter word\n"
            f"Words can be horizontal, vertical, diagonal, forwards, or backwards!\n"
            f"Type each word when you find it, or type `!endwordsearch` to give up.\n\n"
            f"{game.display_grid()}"
        )
        
        await logger.log_command_usage(ctx, "wordsearch", success=True, extra_info=f"Words: {selected_four_letter}, {selected_five_letter}, {selected_six_letter}")
    except Exception as e:
        await logger.log_error(e, "Word Search Error")
        await logger.log_command_usage(ctx, "wordsearch", success=False)

@bot.command(name='endwordsearch')
async def endwordsearch(ctx):
    user_id = ctx.author.id
    if user_id in active_wordsearch_games:
        game = active_wordsearch_games[user_id]
        await ctx.send(f"🛑 Word search ended early. The hidden words were: **{', '.join(game.words)}**")
        del active_wordsearch_games[user_id]
    else:
        await ctx.send("You don't have an active word search game.")

@bot.event
async def on_message(message):
    # --- Word Search Game message handler ---
    if not message.author.bot and message.guild:  # Ensure we have a guild
        user_id = message.author.id
        
        # Check if user has an active game
        if user_id in active_wordsearch_games:
            game = active_wordsearch_games[user_id]
            
            # Skip if message is a command
            if message.content.startswith('!'):
                await bot.process_commands(message)
                return
            
            # Process word guesses
            guesses = [w.strip().lower() for w in re.split(r'[\s,]+', message.content) if w.strip()]
            
            for word_guess in guesses:
                # Check if it's a 4, 5, or 6-letter word
                if (len(word_guess) == 4 or len(word_guess) == 5 or len(word_guess) == 6) and word_guess.isalpha():
                    if game.check_word(word_guess):
                        await message.channel.send(f"✅ Correct! You found **{word_guess}**!")
                        
                        # Check completion after EACH correct word
                        if game.is_complete():
                            # Award points
                            guild_id = str(message.guild.id)
                            user_id_str = str(user_id)
                            record = get_user_record(guild_id, user_id_str)
                            record['points'] += WORDSEARCH_POINTS
                            
                            # Ensure wordsearch_submissions exists
                            if 'wordsearch_submissions' not in record:
                                record['wordsearch_submissions'] = 0
                            record['wordsearch_submissions'] += 1
                            
                            save_pikapoints(pika_data)
                            
                            await message.channel.send(
                                f"🎉 **Congratulations {message.author.mention}!** You found all the words!\n"
                                f"The words were: **{', '.join(game.words)}**\n"
                                f"You earned **{WORDSEARCH_POINTS}** PikaPoints!\n"
                                f"• **Total Points:** {record['points']}\n"
                                f"• **Word Search Games Completed:** {record['wordsearch_submissions']}"
                            )
                            
                            # Clean up
                            del active_wordsearch_games[user_id]
                            
                            # Log completion
                            await logger.log_game_result("Word Search", user_id, guild_id, f"Words: {', '.join(game.words)}")
                            await logger.log_points_award(user_id, guild_id, WORDSEARCH_POINTS, "wordsearch", record["points"])
                            return
                    else:
                        # Only show error if it's not already found
                        if word_guess in game.found_words:
                            await message.channel.send(f"❌ You already found **{word_guess}**!")
                        else:
                            await message.channel.send(f"❌ **{word_guess}** is not one of the hidden words!")
            
            return  # Don't process commands since this was a game guess

# ─── Rhyming Word Game ─────────────────────────────────────────────────

# Add this to your PikaPoints reward values section at the top
RHYME_POINTS = 5

# Store active rhyme games (one per channel)
active_rhyme_games = {}

def get_rhyming_words(target_word, word_list):
    """Get words that rhyme with the target word"""
    rhyming_words = set()
    target_word = target_word.lower()
    
    # Enhanced rhyming logic - check last 2-3 letters
    if len(target_word) >= 3:
        # Get endings to check
        endings_to_check = []
        
        # For 3+ letter words, check last 3 letters
        if len(target_word) >= 3:
            endings_to_check.append(target_word[-3:])
        
        # Always check last 2 letters
        endings_to_check.append(target_word[-2:])
        
        for word in word_list:
            word_lower = word.lower()
            if word_lower != target_word:
                # Check if words rhyme based on endings
                for ending in endings_to_check:
                    if word_lower.endswith(ending):
                        # Additional check: make sure it's not just the same word with a prefix
                        if len(word_lower) >= 3:  # Minimum word length for rhyming
                            rhyming_words.add(word_lower)
                            break
    
    return rhyming_words

@bot.command(name="rhyme")
async def rhyme(ctx):
    try:
        # Check if there's already an active game in this channel
        if ctx.channel.id in active_rhyme_games:
            await ctx.send("❌ There's already an active rhyme game in this channel! Wait for it to finish.")
            return
        
        # Load words from common_words.txt
        with open("common_words.txt") as f:
            common_words_list = [word.strip().lower() for word in f if 4 <= len(word.strip()) <= 6]
        
        # Select a random word that has at least some rhymes
        max_attempts = 50
        target_word = None
        valid_rhymes = set()
        
        for _ in range(max_attempts):
            candidate = random.choice(common_words_list)
            candidate_rhymes = get_rhyming_words(candidate, valid_words)
            if len(candidate_rhymes) >= 3:  # Ensure there are at least 3 possible rhymes
                target_word = candidate
                valid_rhymes = candidate_rhymes
                break
        
        if not target_word:
            await ctx.send("❌ Couldn't find a suitable word for the rhyme game. Please try again.")
            return
        
        # Store game state
        game_state = {
            "target_word": target_word,
            "valid_rhymes": valid_rhymes,
            "submissions": {},  # {user: set of words}
            "channel_id": ctx.channel.id,
            "guild_id": ctx.guild.id,
            "start_time": asyncio.get_event_loop().time()
        }
        active_rhyme_games[ctx.channel.id] = game_state
        
        await ctx.send(
            f"🎵 **Rhyming Game Started!**\n"
            f"Find words that rhyme with: **{target_word.upper()}**\n"
            f"You have 12 seconds to submit as many rhyming words as possible!\n"
            f"Just type the words (no commands needed).\n"
            f"Anyone can participate!"
        )
        
        # Start collecting submissions
        end_time = asyncio.get_event_loop().time() + 12.0
        
        while asyncio.get_event_loop().time() < end_time:
            try:
                remaining_time = end_time - asyncio.get_event_loop().time()
                if remaining_time <= 0:
                    break
                    
                msg = await bot.wait_for(
                    "message",
                    timeout=remaining_time,
                    check=lambda m: (
                        m.channel.id == ctx.channel.id and
                        not m.author.bot and
                        not m.content.startswith('!')
                    )
                )
                
                user = msg.author
                word_guess = msg.content.strip().lower()
                
                # Skip if not a single word
                if ' ' in word_guess:
                    continue
                
                # Initialize user's submission set if needed
                if user not in game_state["submissions"]:
                    game_state["submissions"][user] = set()
                
                # Check if word is valid and rhymes
                if word_guess in valid_rhymes:
                    if word_guess not in game_state["submissions"][user]:
                        game_state["submissions"][user].add(word_guess)
                        await ctx.send(f"✅ {user.mention} found: **{word_guess}**")
                    else:
                        await ctx.send(f"❌ {user.mention} already submitted **{word_guess}**")
                elif word_guess in valid_words:
                    await ctx.send(f"❌ {user.mention} **{word_guess}** doesn't rhyme with **{target_word}**")
                elif len(word_guess) >= 2 and word_guess.isalpha():
                    await ctx.send(f"❌ {user.mention} **{word_guess}** isn't a valid word")
                    
            except asyncio.TimeoutError:
                break
        
        # Game ended - process results
        del active_rhyme_games[ctx.channel.id]
        
        if not game_state["submissions"]:
            await ctx.send(f"⏲ Time's up! No rhyming words were found for **{target_word}**")
            # Show some examples
            example_rhymes = list(valid_rhymes)[:5]
            if example_rhymes:
                await ctx.send(f"Some words that rhyme with **{target_word}**: {', '.join(example_rhymes)}")
            await logger.log_command_usage(ctx, "rhyme", success=True, extra_info="No submissions")
            return
        
        # Find winner (most rhyming words)
        winner = max(game_state["submissions"].items(), key=lambda x: len(x[1]))
        winner_user, winner_words = winner
        
        # Award points to the winner
        guild_id = str(ctx.guild.id)
        user_id = str(winner_user.id)
        record = get_user_record(guild_id, user_id)
        record["points"] += RHYME_POINTS
        
        # Ensure rhyme_submissions field exists
        if "rhyme_submissions" not in record:
            record["rhyme_submissions"] = 0
        record["rhyme_submissions"] += 1
        
        save_pikapoints(pika_data)
        
        # Send results
        result_msg = f"🎵 **Rhyming Game Complete!**\n"
        result_msg += f"The word was: **{target_word}**\n\n"
        
        # Show all participants and their words
        for user, words in sorted(game_state["submissions"].items(), key=lambda x: len(x[1]), reverse=True):
            if user == winner_user:
                result_msg += f"🏆 **{user.display_name}**: {len(words)} words - {', '.join(sorted(words))}\n"
            else:
                result_msg += f"• **{user.display_name}**: {len(words)} words - {', '.join(sorted(words))}\n"
        
        result_msg += f"\n**{winner_user.display_name}** earned **{RHYME_POINTS}** PikaPoints!\n"
        result_msg += f"• **Total Points:** {record['points']}\n"
        result_msg += f"• **Rhyme Games Won:** {record['rhyme_submissions']}"
        
        await ctx.send(result_msg)
        
        # Log the game result
        await logger.log_game_result("Rhyme Game", winner_user.id, guild_id, 
                                   f"Target: {target_word}, Words found: {len(winner_words)}")
        await logger.log_points_award(winner_user.id, guild_id, RHYME_POINTS, "rhyme", record["points"])
        await logger.log_command_usage(ctx, "rhyme", success=True, 
                                     extra_info=f"Winner: {winner_user.display_name}, Words: {len(winner_words)}")
        
    except Exception as e:
        # Clean up on error
        if ctx.channel.id in active_rhyme_games:
            del active_rhyme_games[ctx.channel.id]
        await logger.log_error(e, "Rhyme Game Error")
        await logger.log_command_usage(ctx, "rhyme", success=False)
        await ctx.send("❌ An error occurred in the rhyme game. Please try again.")
    
    # --- Workshop points logic ---
    valid_days = {"monday", "tuesday", "thursday", "friday"}
    if (
        message.guild is not None and
        is_workshop_channel(message.channel) and
        not message.author.bot
    ):
        content_lower = message.content.lower()
        if any(day in content_lower for day in valid_days):
            guild_id = str(message.guild.id)
            user_id_str = str(message.author.id)
            record = get_user_record(guild_id, user_id_str)
            record['points'] += WORKSHOP_POINTS
            if 'workshop_submissions' not in record:
                record['workshop_submissions'] = 0
            record['workshop_submissions'] += 1
            save_pikapoints(pika_data)
            try:
                await message.channel.send(
                    f"🎉 {message.author.mention}, you earned **{WORKSHOP_POINTS}** PikaPoints for participating in the weekly workshop!\n"
                    f"• **Total Points:** {record['points']}\n"
                    f"• **Workshop Submissions:** {record['workshop_submissions']}"
                )
                await logger.log_command_usage(message, "workshop_auto_award", success=True, extra_info="Workshop message detected.")
            except Exception as e:
                await logger.log_error(e, "Workshop Points Award Error")
    
    # Process commands as usual
    await bot.process_commands(message)

# ─── Journal System ─────────────────────────────────────────────────

prompt_prompts = [
    "What were your childhood career dreams/goals? How do they compare to what you want to do now?",
    "Which year comes to mind when you think about the best nostalgia? Why did that year carry the best memories?",
    "Describe your childhood in one word, or a single phrase. If this inspires you to talk more about it, go ahead.",
    "What posters did you have on your wall growing up or want to have?",
    "What instance immediately comes to mind when you remember a meaningful display of kindness?",
    "Who are some people in history you admire?",
    "Who was your first best friend? Tell me about them. Why did you get along so well?",
    "Who was your first love? Tell me about them. Why did they stand out more than others?",
    "What was your first job and when did you get it? What do you wish it would've been?",
    "Describe the experience of your first kiss or first time.",
    "Describe the experience of your first time being drunk/high.",
    "Have you ever gotten in trouble with the law? If you were to, what would it most likely be for?",
    "What was the age you actually became an adult, if you feel you have.",
    "Who or what has had the greatest impact on your life, negatively or positively?",
    "What's one of the hardest things you've ever had to do? Do you regret it or did it need to be done?",
    "If I could do it all over again, I would change...",
    "The teacher that had the most influence on my life was...",
    "Describe your parents, how you feel about them, and how they've influenced you.",
    "The long-lost childhood possession that I would love to see again is...",
    "The one thing I regret most about my life or decisions is...",
    "Some things I've been addicted to include...",
    "I was most happy when...",
    "I will never forgive...",
    "Something I'm glad I tried but will never do again is...",
    "The 3-5 best things I've ever had or done in my life are...",
    "The 3-5 things I want to do but have never done are...",
    "I wish I never met...",
    "The one person I've been most jealous of is...",
    "Someone I miss is...",
    "The last time I said I love you was...",
    "Describe your greatest heartbreak or loss.",
    "Something I feel guilty about is...",
    "My life story in 3 sentences is...",
    "My top 3 favorite bands are...",
    "My top 3 favorite songs are...",
    "My top 3 favorite movies are...",
    "My top 3 favorite TV shows are...",
    "My top 3 favorite books are...",
    "My top 3 favorite games are...",
    "My top 3 favorite places I've been are...",
    "My top 3 favorite foods are...",
    "My top 3 favorite colors are...",
    "My top 3 favorite animals are...",
    "My top 3 favorite drinks are...",
    "My top 3 favorite desserts are...",
    "My top 3 favorite snacks are...",
    "My top 3 favorite celebrities are...",
    "What time period would you most like to live in and why?",
    "What would 16 year old think of current you?",
    "How was it getting your license? If you don't have it, why not?",
    "What's the most embarrassing thing you've ever done?",
    "What's something you've gotten an award for?",
    "Do you regret any of your exes?",
    "What's your political affiliation and why?",
    "Have you ever been in a fight?",
    "Have you ever saved someone's life?",
    "Something you need to confess to someone who won't know is...",
    "First word you'd use to describe yourself is...",
    "First person you think to confide in and why is...",
    "When did you last cry and why?",
    "What's the first quality you look for in a person?",
    "When's the last time you felt in control of your life?",
    "When's a time you successfully stood your ground?",
    "When's the last time you felt proud of yourself?",
    "When's the last time you were scared for your life?",
    "When's the last time you wanted to end your life?",
    "Three signs of hope for your future are...",
    "Three things you forgive yourself for are...",
]

last_prompt_prompt = None 

@bot.command(name='prompt')
async def prompt(ctx):
    try:
        global last_prompt_prompt
        choices = prompt_prompts.copy()
        if last_prompt_prompt in choices:
            choices.remove(last_prompt_prompt)
        if not choices:
            choices = prompt_prompts.copy()
        prompt = random.choice(choices)
        last_prompt_prompt = prompt
        await ctx.send(f"📝 **Journaling prompt:** {prompt}")
        await logger.log_command_usage(ctx, "prompt", success=True, extra_info=f"Prompt: {prompt[:50]}...")
    except Exception as e:
        await logger.log_error(e, "Journal Command Error")
        await logger.log_command_usage(ctx, "prompt", success=False)

@bot.command(name='write')
async def write(ctx, *, entry: str):
    try:
        guild_id = str(ctx.guild.id)
        user_id  = str(ctx.author.id)

        record = get_user_record(guild_id, user_id)
        record['points'] += PROMPT_POINTS
        if 'prompt_submissions' not in record:
            record['prompt_submissions'] = 0
        record['prompt_submissions'] += 1
        save_pikapoints(pika_data)

        await ctx.send(
            f"✅ Entry received! You earned **{PROMPT_POINTS}** PikaPoints!\n"
            f"• **Total Points:** {record['points']}\n"
            f"• **Journal Entries:** {record['prompt_submissions']}"
        )
        
        await logger.log_command_usage(ctx, "write", success=True, extra_info=f"Entry length: {len(entry)} chars")
        
    except Exception as e:
        await logger.log_error(e, "Write Command Error")
        await logger.log_command_usage(ctx, "write", success=False)

# ─── Vent System ─────────────────────────────────────────────────

VENT_FILE = os.path.join(DISK_PATH, "vent_submissions.json")

def load_vent_submissions():
    if not os.path.exists(VENT_FILE):
        with open(VENT_FILE, "w") as f:
            json.dump({}, f)
    with open(VENT_FILE, "r") as f:
        return json.load(f)

def save_vent_submissions(data: dict):
    with open(VENT_FILE, "w") as f:
        json.dump(data, f)
        f.flush()
        os.fsync(f.fileno())

vent_data = load_vent_submissions()

last_vent_message = None

@bot.command(name='vent')
async def vent(ctx):
    try:
        global last_vent_message
        supportive_messages = [
            "Hey, I'm proud of you for reaching out! I'm here to support you. Type your vent and submit it with `!venting [your message]`.",
            "You can rant here, no judgment. When you're ready, use `!venting [your message]` to share.",
            "Sometimes you just need to get it out, we get it. Use `!venting [your message]` to tell me what's up.",
            "I'm here to listen. Let it all out, and know we're here for you. When you're ready, use `!venting [your message]` to share your thoughts."
        ]
        for _ in range(5):
            msg = random.choice(supportive_messages)
            if msg != last_vent_message:
                break
        last_vent_message = msg
        await ctx.send(f"🫂 {msg}")
        await logger.log_command_usage(ctx, "vent", success=True)
    except Exception as e:
        await logger.log_error(e, "Vent Command Error")
        await logger.log_command_usage(ctx, "vent", success=False)

@bot.command(name='venting')
async def venting(ctx, *, entry: str):
    try:
        # Try to delete the user's message for privacy
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            await ctx.send("⚠️ I don't have permission to delete your message. Your vent is still private to me.")
        except Exception:
            pass  # Ignore other errors

        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        # Load or create user's vent list
        if guild_id not in vent_data:
            vent_data[guild_id] = {}
        if user_id not in vent_data[guild_id]:
            vent_data[guild_id][user_id] = []
        # Save the vent entry
        vent_data[guild_id][user_id].append({
            "entry": entry,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        save_vent_submissions(vent_data)
        # Award points
        record = get_user_record(guild_id, user_id)
        record['points'] += VENT_POINTS
        if 'vent_submissions' not in record:
            record['vent_submissions'] = 0
        record['vent_submissions'] += 1
        save_pikapoints(pika_data)
        await ctx.send(
            f"✅ Vent received! You earned **{VENT_POINTS}** PikaPoints.\n"
            f"• **Total Points:** {record['points']}\n"
            f"• **Vent Submissions:** {record['vent_submissions']}"
        )
        await logger.log_command_usage(ctx, "venting", success=True, extra_info=f"Entry length: {len(entry)} chars")
    except Exception as e:
        await logger.log_error(e, "Venting Command Error")
        await logger.log_command_usage(ctx, "venting", success=False)

# ─── Support Bot Commands ─────────────────────────────────────────────────

responses = {
    "comfort": [
        "It's okay to feel overwhelmed. Take a deep breath and know that you are not alone. Try reaching out to a resident, we all care about you.",
        "You are loved, even when it feels like the world is against you. Have you tried venting anonymously to Serenity?",
        "Remember, it's okay to ask for help. You don't have to go through this alone. Everyone here would love to be there for you.",
        "If no one told you today, your existence brightens the world, and I'm proud of you. There's not a single thing you need to change right now.",
        "You're doing just fine, by the way. Unproductive, productive, talkative, quiet, whatever happened today, you're doing fine with the tools you have. I'm proud of you!",
    ],
    "suicidal": [
        "Hai love, it's awful that you're feeling this way while you carry such a bright soul. Your feelings are valid, and I know it's frustrating that it probably feels like no one else can relate. I promise you are seen, heard, and sometimes even related to. Your life is valuable, even if it doesn't feel that way right now. Please reach out for help from a resident, you deserve compassion.",
        "You are not alone in this struggle. There are people who care and want to support you. Is there something quick you can do to ease your chaotic mind? Try binge watching that show you've been meaning to see; maybe it'll be a good reason to keep going.",
        "It's okay to not be okay. Why do you feel like your situation is unchangeable? What are some things that you can change for the better? Start really tiny. We don't need to fix everything huge at once.",
        "Your feelings matter, and so do you. Please be kind to yourself, and take care of yourself by feeding your mind nurturing thoughts while you experience emotional turmoil. People care about you and want to see you thrive.",
        "You are not a burden. You are not annoying, useless, or whatever else your mind might be telling you. Your life can turn into a dream. It has meaning, even if you can't see it right now. Please talk to a resident, they might be able to help.",
        "I know it feels like the pain will never end, but it can get better. With desire comes suffering, but you don't have to suffer by yourself. You're not alone in how you're feeling even if it feels like it. How can we help?",
        "Maybe you just want the pain to stop, not your life, and that's okay. Take a second to think about the things you've survived. Now think about how likely it is that you'll survive this, too, knowing how strong you are. You are capable, and full of grace and love that you were meant to share with others. Just look at you here.",  
        "We often forget the many beautiful things we've experienced and seen because of the immense pain we feel. Remember all the small things that make you smile or laugh when you resort to thinking like this. You're valid, but you're also blinded. This world appreciates you, and I know there's lots of things you can appreciate about it.",
    ],
    "anxious": [
        "I'm sorry you're feeling anxious, that's super annoying. Allow yourself to acknowledge your feelings, but don't let them control you. Find something cold to place in your hands or drink, it helps your nervous system noticeably.",
        "You are not the negative thoughts in your head. You have the power to change them. Be kind to yourself, and gently redirect your ruminating. If you can't, find some upbeat music to distract.",
        "Anxiety is a feeling, not a fact. You can learn to manage it. Taking this step is proof. Try to ground yourself, find something cold to focus on, or count each inhale and exhale you take for a couple minutes. List your meals of the week in your head. Whatever you do, be present for a minute and remember that you're safe.",
        "Breathe deeply. Inhale calm, exhale tension. You are safe in this moment. Want to try doing something with your hands? Go play a word game in the bot backyard, or write down your thoughts quickly on a piece of paper or iPad.",
        "It's okay to take a break. Your mental health is just as important as your physical health.",
        "Would you like to talk about what's making you anxious? I'm here to listen. Try letting out some tension; squeeze a small object in your hands, rap out some fast lyrics.",
        "It doesn't feel like it now, but this shitty moment will pass. You are stronger than these emotions. Just sit in it, know that it will pass, and that you're stronger than this fight or flight response. You are capable of handling this.",
    ],
    "addiction": [
        "You are not your addiction. You are a person with value, who simply needs support and understanding. There are many reasons why we turn to substances; would you like to share some of yours? I'm here to listen with nonjudgmental ears.",
        "Recovery is a journey, not a destination, and a really difficult one at that. Every step you take is a step towards healing, and progress isn't linear. I'm proud of you for trying to get better. What are some things you can do to help yourself today?",
        "I am so proud of you for acknowledging your struggle. It takes immense courage to face addiction. Do you need to rant?",
        "Take a second to think about something similar to your substance of choice. What are some hobbies that release the same dopamine? Do you think you could start with small decisions to replace substance use one day with a favorite hobby?",
        "The fact that you want different for yourself is a huge step in your recovery journey. I'm proud of you. Future you is thanking you in several different ways right now. Don't forget to be proud of yourself.",
        "Only after destroying yourself can you understand yourself. You're not alone in this, and this is very mature to reach out for help.",
        "Sometimes it's just not possible to quit cold turkey, and that's okay. Sometimes people need to get sick of it, and you're not there yet! Don't compare yourself; you are fully capable, but you decide when you're ready.",
        "Your sobriety won't happen overnight. Start small and stay kind to yourself. Expecting to see huge results limits your appreciation for your small achievements.",
        "Your worst day clean is better than your best day high. Don't lose sight of yourself chasing a fake feeling.",
        "Remember that little kid you used to be - they are so proud you're still here, fighting the fight that has destroyed you for so long. Keep them proud, and don't participate in the destruction of yourself. All of us care about you and are here, if you feel like venting to us.",
    ],
    "attention": [
        "You are worthy of love and attention, I'm sorry you're not getting it. You're a diamond in the rough, super funny, and probably smarter than your parents. And you look good.",
        "Who the hell isn't paying attention to you? Let's change that. How was your day?",
        "We all need a little extra love. What's got you feeling needy? I'm here to listen.",
        "Your presence matters to us, honey. How can we help you feel welcome?",
        "I have arrived to deliver attention. I'm so glad you woke up today, you make the earth prettier. What did you do today?",
        "What kind of attention do you need? If you're lonely, anxious, or generally struggling, there's a command for a little extra support.",
        "In case no one has meat rode you today, I'm in love with you.",
        "SOMEONE GIVE THIS MF ATTENTION WTF!",
    ],
    "fuckoff": [
        "You're not a vibe bro 😭",
        "NIGGAS BE SO ANNOYING BRO",
        "Someone ban this nigga",
        "Banned",
    ]
}

# Support command functions with logging
def create_support_command(command_name):
    async def support_command(ctx):
        try:
            global_var_name = f"last_{command_name}_response"
            if global_var_name not in globals():
                globals()[global_var_name] = None
            available = responses[command_name]
            for _ in range(5):
                msg = random.choice(available)
                if msg != globals()[global_var_name]:
                    break
            globals()[global_var_name] = msg
            await ctx.send(msg)
            await logger.log_command_usage(ctx, command_name, success=True)
        except Exception as e:
            await logger.log_error(e, f"Support Command Error ({command_name})")
            await logger.log_command_usage(ctx, command_name, success=False)
    return support_command

# Create all support commands
for cmd_name in responses.keys():
    bot.command(name=cmd_name)(create_support_command(cmd_name))

# ─── Hot Take Task ─────────────────────────────────────────────────

@tasks.loop(seconds=HOT_TAKE_INTERVAL)
async def send_hot_take():
    """Send hot takes every 12 hours"""
    try:
        now = time.time()
        
        # Check if we should skip this iteration
        if now - hot_take_state.get("last_sent", 0) < HOT_TAKE_INTERVAL:
            return
            
        channel = bot.get_channel(HOT_TAKE_CHANNEL_ID)
        if not channel:
            print(f"Hot take channel {HOT_TAKE_CHANNEL_ID} not found")
            return
            
        # Pick next hot take from our ordered list
        order = hot_take_state["order"]
        last_index = hot_take_state.get("last_index", -1)
        
        # Find the next index in our order
        if last_index in order:
            current_position = order.index(last_index)
            next_position = (current_position + 1) % len(order)
        else:
            next_position = 0
            
        hot_take_index = order[next_position]
        hot_take = hot_takes[hot_take_index]
        
        # Send the hot take
        await channel.send(f"🔥 **Hot Take:** {hot_take}")
        
        # Update state
        hot_take_state["last_sent"] = now
        hot_take_state["last_index"] = hot_take_index
        
        # If we've gone through all hot takes, reshuffle for next cycle
        if next_position == len(order) - 1:
            random.shuffle(hot_take_state["order"])
            
        save_hot_take_state(hot_take_state)
        
        await logger.log_bot_event("Hot Take Sent", f"Sent hot take #{hot_take_index}")
        
    except Exception as e:
        await logger.log_error(e, "Hot Take Task Error")

@send_hot_take.before_loop
async def before_send_hot_take():
    """Wait until bot is ready and check if we should wait before sending"""
    await bot.wait_until_ready()
    
    # Calculate time since last hot take
    now = time.time()
    last_sent = hot_take_state.get("last_sent", 0)
    time_since_last = now - last_sent
    
    # If not enough time has passed, wait for the remaining time
    if time_since_last < HOT_TAKE_INTERVAL:
        wait_time = HOT_TAKE_INTERVAL - time_since_last
        print(f"Waiting {wait_time:.0f} seconds before next hot take...")
        await asyncio.sleep(wait_time)

# ─── Points Command ─────────────────────────────────────────────────

@bot.command(name='points', help='Display how many PikaPoints you have')
async def points(ctx):
    try:
        if os.path.exists(PIKA_FILE):
            with open(PIKA_FILE, 'r') as f:
                all_data = json.load(f)
        else:
            all_data = {}

        guild_id_str = str(ctx.guild.id)
        guild_data = all_data.get(guild_id_str, {})

        user_id_str = str(ctx.author.id)
        user_record = guild_data.get(user_id_str, {"points": 0})
        user_points = user_record.get("points", 0) if isinstance(user_record, dict) else user_record

        await ctx.send(f'{ctx.author.mention}, you have **{user_points}** PikaPoints!')
        await logger.log_command_usage(ctx, "points", success=True, extra_info=f"User has {user_points} points")
        
    except Exception as e:
        await logger.log_error(e, "Points Command Error")
        await logger.log_command_usage(ctx, "points", success=False)

# ─── Help Command ─────────────────────────────────────────────────

@bot.command(name="pikahelp")
async def pikahelp_command(ctx):
    try:
        pikahelp_text = """
🧠 **Pikabug Commands**:

`!pikahelp` - Show list of Pikabug's commands.
`!chat` - Triggers AI chat with Pikabug. Trained to make you laugh or comfort you during tough times. Memory lasts for current session only (up to 50 messages).
`!prompt` - Sends a journal prompt/question to answer to help with mindfulness. Submissions are rewarded with PikaPoints!
`!write` - Submits your response to the journal prompt/question. Insert it before your answer.
`!vent` - Vent, rant, and complain to Pikabug. This command gets Pika's attention first. Doing so gets you PikaPoints!
`!venting` - Submit your vent to Pikabug for PikaPoints.
`!points` - View how many PikaPoints you get from activity submissions.
`!comfort` — Get a general comfort and support message.
`!suicidal` — Get compassionate support for suicidal thoughts.  
`!anxious` — Get calming and supportive messages for anxiety.  
`!addiction` — Get supportive messages for addiction and substance use struggles.  
`!attention` — Get messages to help with feelings of neglect or invisibility.  
`!fuckoff` — A humorous response to annoying behavior. 
`!unscramble` — Start the word unscrambling game. PikaPoints are rewarded for winners.
`!guess [word]` — Guess the word from the last scramble.
`!hint` — Get a hint for the current unscramble game; there are two hint options.
`!reveal` — Reveal the current word and end the round of the unscramble game.
`!prefixgame` — Start the prefix word game, where you guess words starting with a random 3-letter prefix. PikaPoints are rewarded for winners.
`!wordsearch` - Start a 5x5 word search game. Find two 5-7 letter words hidden in the grid.
`!rhyme` - Start the rhyming words game. PikaPoints are rewarded for winners.
"""
        await ctx.send(pikahelp_text)
        await logger.log_command_usage(ctx, "pikahelp", success=True)
        
    except Exception as e:
        await logger.log_error(e, "Help Command Error")
        await logger.log_command_usage(ctx, "pikahelp", success=False)

# ─── Bot Startup ─────────────────────────────────────────────────

# Run the bot
bot.run(os.getenv("DISCORD_TOKEN"))
