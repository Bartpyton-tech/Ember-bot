import discord
from discord import app_commands
import os
from dotenv import load_dotenv
import logging
from flask import Flask
import threading

# ===== LOGI =====
logging.basicConfig(level=logging.INFO)

# ===== ENV =====
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ===== DISCORD =====
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ===== FLASK (WYMAGANE DLA RENDER WEB SERVICE) =====
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot działa"

def run_web():
    port = int(os.environ.get("PORT", 10000))  # <<< NAJWAŻNIEJSZE
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()

# ===== READY =====
@client.event
async def on_ready():
    guild = discord.Object(id=1410955423648845825)  # ID twojego serwera
    await tree.sync(guild=guild)
    logging.info(f"Zalogowano jako {client.user}")

# ===== KOMENDA =====
@tree.command(
    name="rollbackstworz",
    description="Tworzy kanał rollback i wysyła instrukcję"
)
async def rollbackstworz(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔧 Rollback",
        description=(
            "**Na czym i co ma na celu stworzenie rollbacka?**\n"
            "Tworzycie rollbacka tylko z myślą o to, żeby polepszyć swoje "
            "umiejętności gry, razem z zarządem będziemy dokładnie analizować "
            "wysyłane przez was klipy i podpowiadać wam co mogliście zrobić "
            "lepiej.\n\n"
            "**Jak wysłać klipa?**\n"
            "Wrzuć całe nagranie (np. MCL) oraz timecodes z momentami fightów."
        ),
        color=0x7B3FE4
    )

    await interaction.response.send_message(embed=embed)

# ===== START =====
client.run(TOKEN)


