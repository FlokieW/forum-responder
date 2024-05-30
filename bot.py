import discord
from discord.ui import Button, View
from openai import OpenAI

import os
from dotenv import load_dotenv

import asyncio

# Load environment variables from .env file
load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DISMISS_ROLES = [int(role_id) for role_id in os.getenv('DISMISS_ROLES', '').split(',') if role_id]
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID'))

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
                dismissed_message_content = interaction.message.content
                await interaction.message.delete()
                await interaction.response.send_message("Message dismissed.", ephemeral=True)
                log_channel = self.client.get_channel(LOG_CHANNEL_ID)
                await log_channel.send(f"""
### <:util_Cross_Box:1180190758075125940> Message dismissed
> **User:** `{interaction.user.id}`
> **Thread:** `{self.thread_id}`
> **Dismissed message:**
```{dismissed_message_content}```
                """)
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

        # Add a delay before processing the thread
        await asyncio.sleep(1)

        # Get the initial post that created the thread
        messages = [message async for message in thread.history(limit=1)]
        if not messages:
            return

        self.thread_creators[thread.id] = messages[0].author.id
        initial_post = f"Thread title: {thread.name}\n\n{messages[0].content}"

        # Check if there are any attachments in the message
        attachment_urls = [attachment.url for attachment in messages[0].attachments]

        async with thread.typing():
            user_content = [
                {"type": "text", "text": f"{initial_post}"}
            ]
            for attachment_url in attachment_urls:
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"{attachment_url}",
                    },
                })
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": [
                            {"type": "text", "text": """    You are a support agent in the VALORANT Discord server. You are helping a player who has created a thread in a forum channel. You cannot have a conversation with the player and can only send one message so do not ask for more information. Do your best to resolve the players' issue or answer their question. Answer in a natural, human-like manner but try to keep your answers concise and within 200 words. You do not need to greet the user. Always add the following message at the end of your response: '>>> I am an AI and I can make mistakes, please verify my answer. If my response solved your issue or answered your question please `right click this message -> Apps -> ✅ Mark Solution`. Thank you!'

            ### Knowledge Base

            Riot Games support: https://support-valorant.riotgames.com/hc/en-us

            <Error codes>
            0, 1, 38, VAN 0, VAN 1, VAN 6: "Connection error. Restart VALORANT and the Riot Client."
            4: "Invalid Riot ID. Change it here. (https://account.riotgames.com/#riot-id)"
            5, 44, 45: "Vanguard issue. Restart VALORANT and the Riot Client. If it persists, uninstall Riot Vanguard, then restart VALORANT. If it still persists, It is most likely due to problematic software running in the background with Vanguard."
            7: "Possible account suspension. Check your email or the VALORANT Discord/Support Site. It also could be a problem with your network. Try running in admin cmd 'netsh int ip reset, ipconfig /release, ipconfig /renew, ipconfig /flushdns, netsh winsock reset'"
            8-21, 31, 33, 43, 46, 49-70, 81, 128, VAN -81, VAN -102, VAN -104: "Problems with the Vanguard. Try reinstalling it."
            VAN 128: "Currently a temporary bug and is being worked on by Riot. In the meantime you can make a ticket for the most recent updates."
            29: "Network issue. Allow VALORANT through your firewall. More details here. (https://support-valorant.riotgames.com/hc/en-us/articles/360048522893-Your-Firewall-VS-VALORANT)"
            39: "Server maintenance. Try again later."
            52-58, 60, 62-70:"Restart the Riot Client. If the problem persists, check the Support Site banners."
            138, VAN 138: "Cannot run on a virtual machine. Install on a regular instance of Windows."
            152, VAN 152: "Hardware ban. Typically lasts 4 months. Submit a ticket if needed."
            VAN9001, VAN9002, VAN9003, VAN9005, VAN9006: "Configuration issues with Secure Boot, TPM, or Windows version. Enable Secure Boot / TPM or Update Windows for VAN9006. Follow the relevant support articles. (https://support-valorant.riotgames.com/hc/en-us/articles/16941220890899-Addressing-Virtualization-based-security-VBS-settings-on-Windows-10-VAN9005-VALORANT), (https://support-valorant.riotgames.com/hc/en-us/articles/10088435639571-Troubleshooting-the-VAN9001-or-VAN-9003-Error-on-Windows-11-VALORANT), (https://support-valorant.riotgames.com/hc/en-us/articles/22291331362067-Vanguard-Restrictions)"""}
                        ]
                    },
                    {
                        "role": "user",
                        "content": user_content,
                    }
                ],
                max_tokens=2000,
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