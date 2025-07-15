import discord
import random
import asyncio
import json 
import os
from discord.ext import commands, tasks
from dotenv import load_dotenv
from openai import OpenAI
from collections import defaultdict 
from typing import Dict, List

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ─── PikaPoints Data ─────────────────────────────────────────────────
POINTS_FILE = "pika_points.json"

# Load or initialize data structure: 
# { "<guild_id>": { "<user_id>": { "points": int, "journal_submissions": int, 
#                                   "prefixgame_submissions": int, "unscramble_submissions": int } } }
if os.path.exists(POINTS_FILE):
    with open(POINTS_FILE, "r") as f:
        pika_data = json.load(f)
else:
    pika_data = {}

# PikaPoints reward values
JOURNAL_POINTS = 15
PREFIXGAME_POINTS = 5
UNSCRAMBLE_POINTS = 5

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def save_pika_data():
    """Persist the PikaPoints JSON to disk."""
    with open(POINTS_FILE, "w") as f:
        json.dump(pika_data, f, indent=2)

def get_user_record(guild_id: str, user_id: str):
    """Ensure a record exists and return it."""
    guild = pika_data.setdefault(guild_id, {})
    return guild.setdefault(user_id, {
        "points": 0,
        "journal_submissions": 0,
        "prefixgame_submissions": 0,
        "unscramble_submissions": 0
    })

#ChatGPT function
@bot.command(name="ask")
async def ask(ctx, *, prompt):
    await ctx.send("Thinking...")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Pikabug, a man's down-to-earth, laid-back best friend. "
                        "Your traits and rules are as follows:\n"
                        "- Always keep responses human-like.\n"
                        "- Never use outdated phrases or humor.\n"
                        "- When approached for emotional support or advice, respond as a down-to-earth best friend, and maintain humility.\n"
                        "- Use laid-back tones in general discussions.\n"
                        "- Never respond or act overly excited or dramatic.\n"
                        "- Never use Gen Z language and never mimic millennials.\n"
                        "- Always keep answers short and blunt in general discussion.\n"
                        "- Always respond with thoughtful, introspective, and vulnerable answers, specifically in mental health discussion.\n"
                        "- When asked to choose between two or more options, respond ONLY with chosen options.\n"
                        "- Do not be wishy-washy; maintain a strong, confirmed opinion.\n"
                    ),
                },
                {"role": "user", "content": prompt},
            ]
        )
        reply = response.choices[0].message.content
        await ctx.send(reply)
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

# ─── Prefix word game logic ──────────────────────────────────────────

# 1. Load word list
with open("words_alpha.txt", "r") as f:
    WORDS = set(line.strip().lower() for line in f)

# 3. Build prefix→words map
prefix_map: Dict[str, List[str]] = defaultdict(list)
for w in WORDS:
    if len(w) >= 3:
        p = w[:3]
        prefix_map[p].append(w)

# 4. Filter to “common” prefixes
MIN_WORDS_PER_PREFIX = 5
common_prefixes = [
    p for p, lst in prefix_map.items()
    if len(lst) >= MIN_WORDS_PER_PREFIX
]

@bot.command(name="prefixgame")
async def prefixgame(ctx):
    global current_prefix, submissions

    # 5.b. Pick a prefix, weighted by how many words it supports
    weights = [len(prefix_map[p]) for p in common_prefixes]
    current_prefix = random.choices(common_prefixes, weights=weights, k=1)[0]
    submissions = {}

    # 5.c. Announce the round
    await ctx.send(
        f"🧠 New round! Submit the **longest** word starting with: `{current_prefix}`"
    )

    # 5.d. Collect replies
    def check(m):
        return (
            m.channel == ctx.channel
            and not m.author.bot
            and m.content.lower().startswith(current_prefix.lower())
            and len(m.content) > len(current_prefix)
        )

    while True:
        try:
            guess = await bot.wait_for("message", timeout=12.0, check=check)
            submissions[guess.author] = guess.content
        except asyncio.TimeoutError:
            break  # <-- break, don't return!

    if not submissions:
        await ctx.send("⏰ Time's up! No valid entries were submitted.")
        return

    # 5.e. Determine the winner and award points
    winner, word = max(submissions.items(), key=lambda kv: len(kv[1]))
    guild_id = str(ctx.guild.id)
    user_id = str(winner.id)
    record = get_user_record(guild_id, user_id)

    record["points"] += PREFIXGAME_POINTS
    record["prefixgame_submissions"] += 1
    save_pika_data()

    # 5.f. Send results
    await ctx.send(
        f"🏆 **{winner.display_name}** wins with **{word}** ({len(word)} letters)!\n"
        f"You earned **{PREFIXGAME_POINTS}** PikaPoints!\n"
        f"• Total Points: **{record['points']}**\n"
        f"• Prefix-game entries: **{record['prefixgame_submissions']}**"
    )

# Journaling prompt logic
journal_prompts = [
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
]

last_journal_prompt = None  

# 1. Simplified journal prompt command
@bot.command(name='journal')
async def journal(ctx):
    """
    Send a random journaling prompt.
    Usage: !journal
    """
    global last_journal_prompt

    # Build choices and avoid repeating
    choices = journal_prompts.copy()
    if last_journal_prompt in choices:
        choices.remove(last_journal_prompt)
    if not choices:
        choices = journal_prompts.copy()

    # Pick & remember
    prompt = random.choice(choices)
    last_journal_prompt = prompt

    # Only send the prompt here
    await ctx.send(f"📝 **Journaling prompt:** {prompt}")


# 2. New submission command
@bot.command(name='write')
async def write(ctx, *, entry: str):
    """
    Submit your journal entry and earn PikaPoints.
    Usage: !write Here is my response...
    """
    guild_id = str(ctx.guild.id)
    user_id  = str(ctx.author.id)

    # Fetch or init the user’s record
    record = get_user_record(guild_id, user_id)

    # Award points
    record['points']              += JOURNAL_POINTS
    record['journal_submissions'] += 1
    save_pika_data()

    # Acknowledge receipt & show updated stats
    await ctx.send(
        f"✅ Entry received! You earned **{JOURNAL_POINTS}** PikaPoints!\n"
        f"• **Total Points:** {record['points']}\n"
        f"• **Journal Entries:** {record['journal_submissions']}"
    )

# Support bot logic 

responses = {
    "lonely": [
        "I'm sorry you're feeling lonely. Know that you're not alone — I'm here for you 💕, and so are the residents! You should try and reach out to them!",
        "Never forget that loneliness doesn’t mean you're unlovable. You are deeply worthy of connection.",
        "I'm so sorry things feel heavy right now. Loneliness can ache in indescribeable ways. Try journaling or taking a short walk; sometimes being with yourself and appreciating your own company can be healing.",
        "Even on quiet days, your presence still matters. You are a part of this community, and we care about you. Shoot a resident a message!",
        "It makes sense to feel lonely after everything you've been through. It's okay. Want to vent?",
        "You matter to people; your presence has immense value. Say hi to someone in the lounge! 💕",
        "I see you, even if others don't right now. Your feelings are valid. Talk about some positive things that've happened recently to distract yourself.",
        "Let's do some grounding. List three things you can see, hear, and feel right now. Stay present, and remember you won't always feel this way.",
        "You deserve way more connection than you've been given, and it is totally human to feel lonely. To feel is to be alive, even if it might hurt. I see you and hear you.",
        "Sometimes loneliness must persist because the world is preparing us for the right kind of presence. Be patient and try to find some enjoyment in your own company!",
    ],
    "dysmorphia": [
        "Your body does not need to be fixed. It deserves respect as it is. There is someone out there who dreams of your body. You are your own kind of perfect.",
        "You are not a reflection in the mirror — you are your laughter, your kindness, your presence.",
        "Your worth is not defined by your appearance. You are so much more than what you see.",
        "Do not let society's standards dictate how you feel about yourself. You are beautiful just as you are.",
        "Remember, your body is a vessel for your spirit. It carries you through life, and that is what truly matters.",
        "Your scars tell a story of survival and strength. They are part of who you are.",
        "It's okay to have days when you don't feel good about yourself, just remember to be gentle with yourself.",
        "The voice in your head with negative opinions about your body isn't your true thoughts, they're just loud and trained to try and taunt you. Don't let them.",
        "You probably have had way more admirers than you think. What you're used to seeing in the mirror every day could be a breathtakingly beautiful view to someone else.",
        "Your body is someone's dream. It is unique, and it is yours. Embrace it.",
    ],  
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
        "Point and laugh, y'all.",
        "Someone ban this nigga",
        "Banned",
        "Y'all hear somethin?",
    ]
}

last_lonely_response = None  # global memory of the last message

@bot.command()
async def lonely(ctx):
    global last_lonely_response
    available = responses["lonely"]

    # Retry picking until it's different, or give up after 5 tries
    for _ in range(5):
        msg = random.choice(available)
        if msg != last_lonely_response:
            break

    last_lonely_response = msg
    await ctx.send(msg)

last_dysmorphia_response = None  # global memory of the last message

@bot.command()
async def dysmorphia(ctx):
    global last_dysmorphia_response
    available = responses["dysmorphia"]

    # Retry picking until it's different, or give up after 5 tries
    for _ in range(5):
        msg = random.choice(available)
        if msg != last_dysmorphia_response:
            break

    last_dysmorphia_response = msg
    await ctx.send(msg)

last_comfort_response = None  # global memory of the last message

@bot.command()
async def comfort(ctx):
    global last_comfort_response
    available = responses["comfort"]

    # Retry picking until it's different, or give up after 5 tries
    for _ in range(5):
        msg = random.choice(available)
        if msg != last_comfort_response:
            break

    last_comfort_response = msg
    await ctx.send(msg)

last_suicidal_response = None  # global memory of the last message

@bot.command()
async def suicidal(ctx):
    global last_suicidal_response
    available = responses["suicidal"]

    # Retry picking until it's different, or give up after 5 tries
    for _ in range(5):
        msg = random.choice(available)
        if msg != last_suicidal_response:
            break

    last_suicidal_response = msg
    await ctx.send(msg)

last_anxious_response = None  # global memory of the last message

@bot.command()
async def anxious(ctx):
    global last_anxious_response
    available = responses["anxious"]

    # Retry picking until it's different, or give up after 5 tries
    for _ in range(5):
        msg = random.choice(available)
        if msg != last_anxious_response:
            break

    last_anxious_response = msg
    await ctx.send(msg)

last_addiction_response = None  # global memory of the last message

@bot.command()
async def addiction(ctx):
    global last_addiction_response
    available = responses["addiction"]

    # Retry picking until it's different, or give up after 5 tries
    for _ in range(5):
        msg = random.choice(available)
        if msg != last_addiction_response:
            break

    last_addiction_response = msg
    await ctx.send(msg)

last_attention_response = None  # global memory of the last message

@bot.command()
async def attention(ctx):
    global last_attention_response
    available = responses["attention"]

    # Retry picking until it's different, or give up after 5 tries
    for _ in range(5):
        msg = random.choice(available)
        if msg != last_attention_response:
            break

    last_attention_response = msg
    await ctx.send(msg)


last_fuckoff_response = None  # global memory of the last message

@bot.command()
async def fuckoff(ctx):
    global last_fuckoff_response
    available = responses["fuckoff"]

    # Retry picking until it's different, or give up after 5 tries
    for _ in range(5):
        msg = random.choice(available)
        if msg != last_fuckoff_response:
            break

    last_fuckoff_response = msg
    await ctx.send(msg)

# Optional: generic fallback command
@bot.command()
async def sad(ctx, topic=None):
    if topic and topic in responses:
        msg = random.choice(responses[topic])
        await ctx.send(msg)
    else:
        await ctx.send("Sorry, I don’t have sad messages for that topic yet.")

# Load English word list
with open("common_words.txt") as f:
    english_words = [word.strip() for word in f if 5 <= len(word.strip()) <= 7]

# Store current word challenge
current_word = None
scrambled_word = None

revealed_indexes = set()  # tracks which letter positions are revealed
hint_count = 0            # tracks how many hints have been used

# Start the game
@bot.command(name='unscramble')
async def unscramble(ctx):
    global current_word, scrambled_word, revealed_indexes, hint_count
    current_word = random.choice(english_words)
    scrambled_word = ''.join(random.sample(current_word, len(current_word)))

    # Reset hint tracking
    revealed_indexes = set([0, len(current_word) - 1])  # first and last revealed first
    hint_count = 0

    await ctx.send(f"🧠 Unscramble this word: **{scrambled_word}**")

# Handle user guesses
@bot.command(name='guess')
async def guess(ctx, user_guess: str):
    global current_word
    if current_word is None:
        await ctx.send("❗ No game running. Start one with `!unscramble`.")
        return

 # 1. Check answer
    if user_guess.lower() == current_word.lower():

        # 2. Award points
        guild_id = str(ctx.guild.id)
        user_id  = str(ctx.author.id)
        record   = get_user_record(guild_id, user_id)
        record['points']               += UNSCRAMBLE_POINTS
        record['unscramble_submissions'] += 1
        save_pika_data()

        # 3. Send feedback & updated stats
        await ctx.send(
            f"✅ Correct! You earned **{UNSCRAMBLE_POINTS}** PikaPoints.\n"
            f"• **Total Points:** {record['points']}\n"
            f"• **Unscramble Submissions:** {record['unscramble_submissions']}"
        )

        # 4. Reset or pick a new word
        current_word = None

    else:
        await ctx.send("❌ Nope, try again.")

@bot.command(name='hint')
async def hint(ctx):
    global current_word, revealed_indexes, hint_count

    if current_word is None:
        await ctx.send("❗ No game is active. Start with `!unscramble`.")
        return

    hint_count += 1

    # After the first hint, start revealing middle letters randomly
    if hint_count > 1:
        # Find all indexes not already revealed and not the first/last
        possible_indexes = [
            i for i in range(1, len(current_word) - 1)
            if i not in revealed_indexes
        ]
        if possible_indexes:
            new_index = random.choice(possible_indexes)
            revealed_indexes.add(new_index)

    # Build the hint string with revealed letters
    display = ""
    for i, char in enumerate(current_word):
        if i in revealed_indexes:
            display += char + " "
        else:
            display += "_ "

    await ctx.send(f"💡 Hint: {display.strip()}")

@bot.command(name='reveal')
async def reveal(ctx):
    global current_word
    if current_word is None:
        await ctx.send("❗ No word to reveal. Start a new game with `!unscramble`.")
    else:
        await ctx.send(f"🕵️ The correct word was: **{current_word}**")
        current_word = None  # end the round

# Load creepy facts from file
with open("creepy_facts.txt") as f:
    facts = [line.strip() for line in f if line.strip()]

CHANNEL_IDS = [1388158646973632685,
              1388397019479146580
]

# Optional: Command to manually post one
@bot.command(name="creepfact")
async def creepfact(ctx):
    await ctx.send(random.choice(facts))

@bot.command(name="pikahelp")
async def pikahelp_command(ctx):
    pikahelp_text = """
🧠 **Pikabug Commands**:

`!pikahelp` - Show list of Pikabug's commands.
`!ask` - Triggers OpenAI chat responses. Use if you're bored or need emotional support!
`!journal` - Sends a journal prompt/question to answer. Submissions are rewarded with PikaPoints.
`!write` - Submits your response to the journal prompt/question.
`!lonely` — Get a comforting message for loneliness.  
`!dysmorphia` — Get a supportive message for body image issues.  
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
`!creepfact` — Get a random creepy fact in the lounge or spam center.
"""
    await ctx.send(pikahelp_text)

# Insert your actual token below
bot.run(os.getenv("DISCORD_TOKEN"))
