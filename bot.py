import discord
import openai
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Set the API key for OpenAI
openai.api_key = OPENAI_API_KEY

intents = discord.Intents.default()
intents.message_content = True

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ready(self):
        print(f'Logged in as {self.user}')

    async def on_thread_create(self, thread):
        # Ensure this is in the specific forum channel ID and not a typical thread
        forum_channel_id = 1245267823132151899  # Replace with your forum channel ID
        if isinstance(thread.parent, discord.ForumChannel) and thread.parent.id == forum_channel_id:
            print(f'Thread created: {thread.name} in forum {thread.parent.name}')
            await self.handle_thread_creation(thread)

    async def handle_thread_creation(self, thread):
        # Get the initial post that created the thread
        messages = [message async for message in thread.history(limit=1)]
        if not messages:
            return

        initial_post = messages[0].content

        # Send initial_post content to ChatGPT using the updated API interface
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": initial_post}
            ]
        )

        chatgpt_response = response['choices'][0]['message']['content']

        # Reply in the thread
        await thread.send(chatgpt_response)

client = MyClient(intents=intents)

client.run(DISCORD_TOKEN)