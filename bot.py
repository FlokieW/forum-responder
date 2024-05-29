import discord
from discord.ui import Button, View
from openai import OpenAI

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DISMISS_ROLES = [int(role_id) for role_id in os.getenv('DISMISS_ROLES', '').split(',') if role_id]

openai_client = OpenAI(api_key=OPENAI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True

class CustomDismissButton(Button):
    def __init__(self, client, thread_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client
        self.thread_id = thread_id

    async def callback(self, interaction: discord.Interaction):
        # Check if the user has any of the roles that can dismiss messages
        user_roles = [role.id for role in interaction.user.roles]
        can_dismiss = any(role in user_roles for role in DISMISS_ROLES)

        # Ensure only the thread creator or a user with a dismiss role can dismiss
        if interaction.user.id == self.client.thread_creators.get(self.thread_id) or can_dismiss:
            try:
                await interaction.message.delete()
                await interaction.response.send_message("Message dismissed.", ephemeral=True)
            except discord.errors.NotFound:
                await interaction.response.send_message("This message no longer exists.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
        else:
            try:
                await interaction.response.send_message("You are not able dismiss this message.", ephemeral=True)
            except discord.errors.NotFound:
                await interaction.followup.send("You are not able to dismiss this message.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

class CustomView(View):
    def __init__(self, client, thread_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client
        self.thread_id = thread_id
        self.add_item(CustomDismissButton(client, thread_id, label="Dismiss", style=discord.ButtonStyle.secondary))

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thread_creators = {}

    async def on_ready(self):
        print(f'Logged in as {self.user}')

    async def on_thread_create(self, thread):
        forum_channel_id = int(os.getenv('FORUM_CHANNEL_ID'))
        if isinstance(thread.parent, discord.ForumChannel) and thread.parent.id == forum_channel_id:
            print(f'Thread created: {thread.name} in forum {thread.parent.name}')
            await self.handle_thread_creation(thread)

    async def handle_thread_creation(self, thread):
        # Get the initial post that created the thread
        messages = [message async for message in thread.history(limit=1)]
        if not messages:
            return

        self.thread_creators[thread.id] = messages[0].author.id
        initial_post = f"Thread title: {thread.name}\n\n{messages[0].content}"

        async with thread.typing():
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": """
You are a support agent in the VALORANT Discord server. You are helping a player who has created a thread in a forum channel. You cannot have a conversation with the player and can only send one message so do not ask for more information. Do your best to resolve the players' issue or answer their question. Answer in a natural, human-like manner but try to keep your answers concise and within 200 words. You do not need to greet the user. Always add the following message at the end of your response: '>>> I am an AI and I can make mistakes, please verify my answer. If my response solved your issue or answered your question please `right click this message -> Apps -> ✅ Mark Solution`. Thank you!'

### Knowledge Base

...[full error codes and messages truncated for brevity]...
                     """},
                    {"role": "user", "content": initial_post}
                ],
                max_tokens=2000
            )

        chatgpt_response = response.choices[0].message.content

        # Split the response into chunks of 2000 characters
        response_chunks = [chatgpt_response[i:i + 2000] for i in range(0, len(chatgpt_response), 2000)]

        # Create a view with the dismiss button
        view = CustomView(client=self, thread_id=thread.id)

        # Reply in the thread with the dismiss button
        for chunk in response_chunks:
            await messages[0].reply(chunk, view=view)

discord_client = MyClient(intents=intents)

discord_client.run(DISCORD_TOKEN)