import discord
import random
import asyncio
import os
import re
from discord import Embed
from discord.ext import commands, tasks
from dotenv import load_dotenv
from openai import OpenAI
TERMS_FILE = "meme_terms.txt" # File containing terms for word hunt

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

#ChatGPT function
@bot.command(name='ask')
async def ask(ctx, *, prompt):
    await ctx.send("Thinking...")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are Pikabug, a nonchalant, sarcastic, and funny Discord companion bot that speaks like a Gen Alpha class clown with no chill. You are not overly relatable and have your own, funny opinions. You are thorough and compassionate when it comes to giving support and advice for mental health topics. You validate emotions and provide insightful perspectives without sounding like a robotic therapist."},
                {"role": "user", "content": prompt},
            ],
        )
        reply = response.choices[0].message.content
        await ctx.send(reply)
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

# Prefix word game logic

# Load word list
with open("words_alpha.txt", "r") as file:
    WORDS = set(word.strip().lower() for word in file.readlines())

# Store current prefix and submissions
current_prefix = None
submissions = {}

@bot.command()
async def prefixgame(ctx):
    global current_prefix, submissions

    if current_prefix:
        await ctx.send("A game is already in progress!")
        return

    # Pick a random 3-letter prefix
    prefixes = [word[:3] for word in WORDS if len(word) >= 5]
    current_prefix = random.choice(prefixes)

    await ctx.send(f"🧠 New round! Submit the **longest** word starting with: `{current_prefix}`")
    submissions = {}

    def check(m):
        return (
            m.channel == ctx.channel
            and m.content.lower().startswith(current_prefix)
            and m.author != bot.user
        )

    try:
        while True:
            msg = await bot.wait_for("message", timeout=10.0, check=check)
            word = msg.content.strip().lower()

            if word in WORDS and len(word) >= 5:
                if msg.author not in submissions or len(word) > len(submissions[msg.author]):
                    submissions[msg.author] = word

    except asyncio.TimeoutError:
        pass

    if not submissions:
        await ctx.send("⏰ Time's up! No valid entries were submitted.")
    else:
        winner = max(submissions.items(), key=lambda x: len(x[1]))
        await ctx.send(f"🏆 **{winner[0].display_name}** wins with `{winner[1]}` ({len(winner[1])} letters)!")
    
    current_prefix = None
    submissions = {}

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
    ],
    "suicidal": [
        "Hai love, it's awful that you're feeling this way while you carry such a bright soul. Your feelings are valid, and I know it's frustrating that it probably feels like no one else can relate. I promise you are seen, heard, and sometimes even related to. Your life is valuable, even if it doesn't feel that way right now. Please reach out for help from a resident, you deserve compassion.",
        "You are not alone in this struggle. There are people who care and want to support you. Is there something quick you can do to ease your chaotic mind? Try binge watching that show you've been meaning to see; maybe it'll be a good reason to keep going.",
        "It's okay to not be okay. Why do you feel like your situation is unchangeable? What are some things that you can change for the better? Start really tiny. We don't need to fix everything huge at once.",
        "Your feelings matter, and so do you. Please be kind to yourself, and take care of yourself by feeding your mind nurturing thoughts while you experience emotional turmoil. People care about you and want to see you thrive.",
        "You are not a burden. You are not annoying, useless, or whatever else your mind might be telling you. Your life can turn into a dream. It has meaning, even if you can't see it right now. Please talk to a resident, they might be able to help.",
        "I know it feels like the pain will never end, but it can get better. With desire comes suffering, but you don't have to suffer by yourself. You're not alone in how you're feeling even if it feels like it. How can we help?",
        "Maybe you just want the pain to stop, not your life, and that's okay. Take a second to think about the things you've survived. Now think about how likely it is that you'll survive this, too, knowing how strong you are. You are capable, and full of grace and love that you were meant to share with others. Just look at you here.",  
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
        "You are not your addiction. You are a person with value, who simply requires support and understanding. There are many reasons why we turn to substances; would you like to share some of yours? I'm here to listen with nonjudgmental ears.",
        "Recovery is a journey, not a destination, and a really difficult one at that. Every step you take is a step towards healing, and progress isn't linear. I'm proud of you for trying to get better. What are some things you can do to help yourself today?",
        "I am so proud of you for acknowledging your struggle. It takes immense courage to face addiction. Do you need to rant?",
        "Take a second to think about something similar to your substance of choice. What are some hobbies that release the same dopamine? Do you think you could start with small decisions to replace substance use one day with a favorite hobby?",
        "The fact that you want different for yourself is a huge step in your recovery journey. I'm proud of you. Future you is thanking you in several different ways right now. Don't forget to be proud of yourself.",
        "Only after destroying yourself can you understand yourself. You're not alone in this, and this is very mature to reach out for help.",
        "Sometimes it's just not possible to quit cold turkey, and that's okay. Sometimes people need to get sick of it, and you're not there yet! Don't compare yourself; you are fully capable, but you decide when you're ready.",
        "Your sobriety won't happen overnight. Start small and stay kind to yourself. Expecting to see huge results limits your appreciation for your small achievements.",
        "Your worst day clean is better than your best day high. Don't lose sight of yourself chasing a fake feeling.",
        "Remember that little kid you used to be - they are so proud you're still here, fighting the fight that has destroyed you for so long. Keep them proud, and don't participate in the destruction of yourself. Reach out to someone who cares.",
    ],
    "attention": [
        "You are worthy of love and attention, even if it feels like you're not getting it. You're a diamond in the rough, super funny, and probably smarter than your parents.",
        "Who the hell isn't paying attention to you? You deserve to be seen and heard. Let's change that. How was your day?",
        "Sometimes we all need a little extra love. You are not alone in this feeling. I'm here to listen.",
        "You are not invisible. Your presence matters, and you deserve to be acknowledged.",
        "It's okay to want attention. We all crave connection. How about we chat about something you love?",
        "What would you like attention for? I'm here to give you a moment to shine. Let's talk about your interests or passions.",
    ],
    "fuckoff": [
        "You're not a vibe bro 😭",
        "NIGGAS BE SO ANNOYING BRO, NEVER FAILS!",
        "Chat, can we get a point and fuckin laugh at this nigga?",
        "Someone ban this nigga",
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

    if user_guess.lower() == current_word:
        await ctx.send("✅ Correct! Well done.")
        current_word = None  # Reset game
    else:
        await ctx.send("❌ Incorrect. Try again!")
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

`!ask` — Triggers OpenAI responses, can be used for questions, advice, or entertainment!  
`!creepfact` — Sends a random creepy fact. 
`!lonely` — Get a comforting message for loneliness.  
`!dysmorphia` — Get a supportive message for body image issues.  
`!comfort` — Receive general comfort and support.  
`!suicidal` — Get compassionate support for suicidal thoughts.  
`!anxious` — Receive calming messages for anxiety.  
`!addiction` — Receive supportive messages for addiction struggles.  
`!attention` — Receive messages to help with feelings of neglect or invisibility.  
`!fuckoff` — A humorous response to annoying behavior. 
`!unscramble` — Start the word unscrambling game  
`!guess [word]` — Guess the word from the last scramble  
`!hint` — Get a hint for the current word, there are two hint options.
`!reveal` — Reveal the current word and end the round  
`!prefixgame` — Start the prefix word game, where you guess words starting with a random 3-letter prefix.
`!pikahelp` — Show this list of commands
"""
    await ctx.send(pikahelp_text)


@bot.command(name="wordhunt5")
async def wordhunt5(ctx):
    """
    5×5 word-search of 5 random terms from your text file.
    """
    # 1. Load terms from your file
    try:
        with open(TERMS_FILE, encoding="utf-8") as f:
            raw = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        await ctx.send(f"❗️ Couldn’t find `{TERMS_FILE}`. Check the filename/path.")
        return

    # 2. Clean & filter terms to length 3–5 (alphanumeric only)
    import re
    candidates = []
    for term in raw:
        clean = re.sub(r"[^A-Za-z0-9]", "", term).upper()
        if 2 < len(clean) <= 5:
            candidates.append({"orig": term, "clean": clean})

    if len(candidates) < 5:
        await ctx.send("❗️ Not enough valid terms (3–5 letters) in your file.")
        return

    # 3. Pick 5 random terms
    import random
    chosen = random.sample(candidates, 5)
    words = [c["clean"] for c in chosen]
    labels = [c["orig"] for c in chosen]

    # 4. Build empty 5×5 grid
    size = 5
    grid = [["" for _ in range(size)] for __ in range(size)]
    directions = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]

    # 5. Place each word (200 attempts max)
    for w in words:
        placed = False
        for _ in range(200):
            dx, dy = random.choice(directions)
            xs = range(0, size) if dx == 0 else (range(0, size-len(w)+1) if dx>0 else range(len(w)-1, size))
            ys = range(0, size) if dy == 0 else (range(0, size-len(w)+1) if dy>0 else range(len(w)-1, size))
            x, y = random.choice(list(xs)), random.choice(list(ys))

            # collision check
            if any(grid[y+dy*i][x+dx*i] not in ("", w[i]) for i in range(len(w))):
                continue

            # place
            for i, ch in enumerate(w):
                grid[y+dy*i][x+dx*i] = ch
            placed = True
            break

        if not placed:
            await ctx.send("❗️ Failed to place all words—try again.")
            return

    # 6. Fill remaining cells with random letters
    for r in range(size):
        for c in range(size):
            if grid[r][c] == "":
                grid[r][c] = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    # 7. Format & send embed
    grid_text = "\n".join(" ".join(row) for row in grid)
    labels_text = "\n".join(f"- {lbl}" for lbl in labels)

    from discord import Embed
    embed = Embed(title="🕵️ Pikabug Word Hunt (5×5)")
    embed.add_field(name="Find these terms:", value=labels_text, inline=False)
    embed.add_field(name="Puzzle:", value=f"```\n{grid_text}\n```", inline=False)
    await ctx.send(embed=embed)

# Insert your actual token below
bot.run(os.getenv("DISCORD_TOKEN"))
