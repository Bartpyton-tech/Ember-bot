import discord
from discord import app_commands
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    await tree.sync()
    logging.info(f"Zalogowano jako {client.user}")
from flask import Flask
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot działa"

def run_web():
    app.run(host="0.0.0.0", port=8080)

client.run(TOKEN)
@tree.command(name="rollbackstworz", description="Tworzy kanał rollback i wysyła instrukcję")
async def rollbackstworz(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔧 Rollback",
        description=(
            "**Na czym i co ma na celu stworzenie rollbacka?**\n"
            "Tworzycie rollbacka tylko z myślą o to, żeby polepszyć swoje "
            "umiejętności gry, razem z zarządem będziemy dokładnie analizować "
            "wysyłane przez was klipy i podpowiadać wam co mogliście zrobić "
            "lepiej aby jak najszybciej progresować.\n\n"
            "**Jak macie wysłać poprawnie klipa?**\n"
            "Aby poprawnie wysłać klipa musicie wstawić całe nagranie "
            "z np. MCL na swój stworzony za pomocą przycisku kanał wraz "
            "z rozpisanymi timecodes – momenty gdzie był fight lub coś "
            "ciekawego co uważacie, że jest do poprawy."
        ),
        color=0x7B3FE4
    )

    await interaction.response.send_message(embed=embed)

