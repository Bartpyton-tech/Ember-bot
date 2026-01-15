import discord
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import os
from dotenv import load_dotenv
import logging
from flask import Flask
import threading

# ====== LOGI ======
logging.basicConfig(level=logging.INFO)

# ====== ENV ======
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
PORT = int(os.getenv("PORT", 8080))

# ====== DISCORD ======
intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ====== FLASK (RENDER) ======
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot działa"

def run_web():
    app.run(host="0.0.0.0", port=PORT)

threading.Thread(target=run_web).start()

# ====== DANE ======
captures_data = {}

# ====== MODAL ======
class CaptureModal(Modal, title="Nowy Capt"):
    godzina = TextInput(label="Godzina capta", placeholder="np. 15:45")
    kwadrat = TextInput(label="Kwadrat", placeholder="np. A1, B3")
    rodzina = TextInput(label="Rodzina", placeholder="np. Kowalscy")

    async def on_submit(self, interaction: discord.Interaction):
        captures_data[interaction.id] = {
            "godzina": self.godzina.value,
            "kwadrat": self.kwadrat.value,
            "rodzina": self.rodzina.value,
            "users": []
        }

        embed = discord.Embed(
            title="😡 CAPT | Rodzina: " + self.rodzina.value,
            description=(
                f"🕒 **Godzina:** {self.godzina.value}\n"
                f"📍 **Kwadrat:** {self.kwadrat.value}\n\n"
                f"⚔ **PICKNIEC:**\nBrak"
            ),
            color=0x2b2d31
        )

        await interaction.channel.send(
            content="@everyone",
            embed=embed,
            view=CaptureView(interaction.id)
        )

        await interaction.response.send_message(
            "Capt utworzony ✅",
            ephemeral=True
        )

# ====== VIEW ======
class CaptureView(View):
    def __init__(self, capture_id):
        super().__init__(timeout=None)
        self.capture_id = capture_id

    @Button(label="Zapisz się", style=discord.ButtonStyle.success)
    async def zapisz(self, interaction: discord.Interaction, button: Button):
        data = captures_data[self.capture_id]
        if interaction.user.name not in data["users"]:
            data["users"].append(interaction.user.name)
        await interaction.response.send_message("Zapisałeś się ✅", ephemeral=True)

    @Button(label="Wypisz się", style=discord.ButtonStyle.danger)
    async def wypisz(self, interaction: discord.Interaction, button: Button):
        data = captures_data[self.capture_id]
        if interaction.user.name in data["users"]:
            data["users"].remove(interaction.user.name)
        await interaction.response.send_message("Wypisałeś się ❌", ephemeral=True)

    @Button(label="Wybierz skład", style=discord.ButtonStyle.primary)
    async def sklad(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Funkcja w przygotowaniu 🛠", ephemeral=True)

    @Button(label="Pokaż zapisanych", style=discord.ButtonStyle.secondary)
    async def pokaz(self, interaction: discord.Interaction, button: Button):
        data = captures_data[self.capture_id]
        users = "\n".join(data["users"]) or "Brak zapisanych"
        await interaction.response.send_message(users, ephemeral=True)

    @Button(label="Utwórz kanał rollback", style=discord.ButtonStyle.secondary)
    async def rollback(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Rollbacks")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True),
        }

        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True)

        channel = await guild.create_text_channel(
            name=f"rollback-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        await interaction.response.send_message(
            f"Utworzono kanał {channel.mention} ✅",
            ephemeral=True
        )

# ====== KOMENDA ======
@tree.command(name="captures", description="Utwórz nowy capt")
async def captures(interaction: discord.Interaction):
    await interaction.response.send_modal(CaptureModal())

# ====== READY ======
@client.event
async def on_ready():
    await tree.sync()
    logging.info(f"Zalogowano jako {client.user}")

# ====== START ======
client.run(TOKEN)








