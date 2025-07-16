#ChatGPT function
@bot.command(name="ask")
async def ask(ctx, *, prompt):
    thinking_msg = await ctx.send("Thinking...")

    user_key = f"{ctx.guild.id}-{ctx.author.id}"
    if user_key not in conversation_history:
        conversation_history[user_key] = []

    conversation_history[user_key].append({"role": "user", "content": prompt})
    conversation_history[user_key] = conversation_history[user_key][-30:]  # Keep it tight

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": (
                    "You are Pikabug, a man's down-to-earth, laid-back best friend.\n"
                    "Your traits and rules are as follows:\n"
                    "- Always keep responses human-like.\n"
                    "- Never use outdated phrases or humor.\n"
                    "- When approached for emotional support or advice, respond as a down-to-earth best friend.\n"
                    "- Use laid-back tones in general discussions.\n"
                    "- Never respond or act overly excited or dramatic.\n"
                    "- Never use Gen Z language or mimic millennials.\n"
                    "- Always keep answers short and blunt in general discussion.\n"
                    "- Always respond with thoughtful, introspective, and vulnerable answers in mental health topics.\n"
                    "- When asked to choose between two or more options, respond ONLY with chosen options.\n"
                    "- Do not be wishy-washy; maintain a strong, confirmed opinion.\n"
                )},
                *conversation_history[user_key]
            ]
        )

        reply = response.choices[0].message.content
        conversation_history[user_key].append({"role": "assistant", "content": reply})

        await thinking_msg.edit(content=reply)

    except Exception as e:
        error_msg = f"⚠️ Error occurred: {str(e)}"
        await thinking_msg.edit(content=error_msg)
        print(error_msg)
