import discord
import random
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Define categories and message pools
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
        "If no one told you today, your existence brightens the world, and I'm proud of you. There's not a single thing you need to change right now."
    ],
    "suicidal": [
        "Your life is valuable, even if it doesn't feel that way right now. Please reach out for help, you deserve compassion.",
        "You are not alone in this struggle. There are people who care and want to support you. Talk to a resident!",
        "It's okay to not be okay. Why do you feel like your situation is unchangeable? What are some things that you can change for the better?",
        "Your feelings matter, and so do you. Please take care of yourself. People care and want to see you thrive.",
        "You are not a burden. Your life has meaning, even if you can't see it right now. Please talk to someone who can help.",
        "I know it feels like the pain will never end, but it can get better. With desire comes suffering, but you don't have to suffer by yourself.",
        "Maybe you just want the pain to stop, not your life, and that's okay. Take a second to think about the things you've survived. Now think about how likely it is that you'll survive this, too.",
    ],
    "anxious": [
        "It's okay to feel anxious. Acknowledge your feelings, but don't let them control you.",
        "You are not the negative thoughts in your head. You have the power to change them.",
        "Anxiety is a feeling, not a fact. You can learn to manage it. Taking this step is proof.",
        "Breathe deeply. Inhale calm, exhale tension. You are safe in this moment.",
        "It's okay to take a break. Your mental health is just as important as your physical health.",
        "Would you like to talk about what's making you anxious? I'm here to listen.",
        "It doesn't feel like it now, but this shitty moment will pass. You are stronger than these emotions.",
    ],
    "addiction": [
        "You are not your addiction. You are a person with value, who simply requires support and understanding. There are many reasons why we turn to substances; would you like to share some of yours?",
        "Recovery is a journey, not a destination. Every step you take is a step towards healing, and progress isn't linear. I'm proud of you for trying to get better.",
        "I am so proud of you for acknowledging your struggle. It takes immense courage to face addiction. Do you need to rant?",
        "Take a second to think about something similar to your substance of choice. What are some hobbies that release the same dopamine?",
        "The fact that you want different for yourself is a huge step in your recovery journey. I'm proud of you. Future you is thanking you in several different ways right now.",
        "Only after destroying yourself can you understand yourself. You're not alone in this. Keep going.",
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
        "What do you need attention for? I'm here to give you a moment to shine. Let's talk about your interests or passions.",
    ],

}

# Command template
@bot.command()
async def lonely(ctx):
    msg = random.choice(responses["lonely"])
    await ctx.send(msg)

@bot.command()
async def dysmorphia(ctx):
    msg = random.choice(responses["dysmorphia"])
    await ctx.send(msg)

@bot.command()
async def comfort(ctx):
    msg = random.choice(responses["comfort"])
    await ctx.send(msg)

@bot.command()
async def suicidal(ctx):
    msg = random.choice(responses["suicidal"])
    await ctx.send(msg)

@bot.command()
async def anxious(ctx):
    msg = random.choice(responses["anxious"])
    await ctx.send(msg)

@bot.command()
async def addiction(ctx):
    msg = random.choice(responses["addiction"])
    await ctx.send(msg)

@bot.command()
async def attention(ctx):
    msg = random.choice(responses["attention"])
    await ctx.send(msg)

# Optional: generic fallback command
@bot.command()
async def sad(ctx, topic=None):
    if topic and topic in responses:
        msg = random.choice(responses[topic])
        await ctx.send(msg)
    else:
        await ctx.send("Sorry, I don’t have sad messages for that topic yet.")


import os
bot.run(os.environ["DISCORD_TOKEN"])
