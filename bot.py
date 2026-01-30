import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import logging
from dotenv import load_dotenv
from flask import Flask
import threading

# ====== LOGI ======
logging.basicConfig(level=logging.INFO)

# ====== ENV ======
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
ROLLBACK_CATEGORY_NAME = os.getenv("ROLLBACK_CATEGORY_NAME", "Rollbacks")

# ====== BOT ======
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ====== FLASK (Render) ======
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot działa"

def run_web():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_web).start()

# ====== DANE ======
DATA_FILE = "data/captures.json"

def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ====== READY ======
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    logging.info(f"Zalogowano jako {bot.user}")

# =====================================================
# ==================== CAPTURES =======================
# =====================================================

class CapturesView(discord.ui.View):
    def __init__(self, capt_id):
        super().__init__(timeout=None)
        self.capt_id = capt_id

    @discord.ui.button(label="✅ Zapisz się", style=discord.ButtonStyle.success)
    async def zapisz(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        users = data["captures"][self.capt_id]["users"]

        if interaction.user.id in users:
            await interaction.response.send_message("❌ Już jesteś zapisany.", ephemeral=True)
            return

        users.append(interaction.user.id)
        save_data(data)
        await interaction.response.send_message("✅ Zapisano!", ephemeral=True)

    @discord.ui.button(label="❌ Wypisz się", style=discord.ButtonStyle.danger)
    async def wypisz(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        users = data["captures"][self.capt_id]["users"]

        if interaction.user.id not in users:
            await interaction.response.send_message("❌ Nie jesteś zapisany.", ephemeral=True)
            return

        users.remove(interaction.user.id)
        save_data(data)
        await interaction.response.send_message("✅ Wypisano.", ephemeral=True)

    @discord.ui.button(label="📄 Pokaż zapisanych", style=discord.ButtonStyle.secondary)
    async def pokaz(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        users = data["captures"][self.capt_id]["users"]

        if not users:
            await interaction.response.send_message("Brak zapisanych.", ephemeral=True)
            return

        names = []
        for uid in users:
            member = interaction.guild.get_member(uid)
            if member:
                names.append(member.display_name)

        await interaction.response.send_message(
            "**Zapisani:**\n" + "\n".join(names),
            ephemeral=True
        )

# ====== KOMENDA /captures ======
@tree.command(name="captures", description="Tworzy capt z zapisami", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    rodzina="Nazwa rodziny",
    godzina="Godzina (np. 20:00)",
    kwadrat="Kwadrat (np. G5)"
)
async def captures(
    interaction: discord.Interaction,
    rodzina: str,
    godzina: str,
    kwadrat: str
):
    data = load_data()

    capt_id = f"{rodzina}-{godzina}-{kwadrat}"

    data["captures"][capt_id] = {
        "rodzina": rodzina,
        "godzina": godzina,
        "kwadrat": kwadrat,
        "users": []
    }

    save_data(data)

    embed = discord.Embed(
        title="🚨 CAPT",
        description=(
            f"👨‍👩‍👧 **Rodzina:** {rodzina}\n"
            f"🕒 **Godzina:** {godzina}\n"
            f"📍 **Kwadrat:** {kwadrat}"
        ),
        color=0x7B3FE4
    )

    await interaction.response.send_message(
        embed=embed,
        view=CapturesView(capt_id)
    )

# =====================================================
# =================== ROLLBACK ========================
# =====================================================

class RollbackView(discord.ui.View):
    @discord.ui.button(label="🛠 Utwórz kanał", style=discord.ButtonStyle.primary)
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild

        category = discord.utils.get(guild.categories, name=ROLLBACK_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(ROLLBACK_CATEGORY_NAME)

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
            f"✅ Utworzono kanał {channel.mention}",
            ephemeral=True
        )

@tree.command(name="rollbackstworz", description="Tworzy rollback", guild=discord.Object(id=GUILD_ID))
async def rollbackstworz(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔧 Rollback",
        description="Kliknij przycisk, aby utworzyć prywatny kanał rollback.",
        color=0x7B3FE4
    )

    await interaction.response.send_message(
        embed=embed,
        view=RollbackView()
    )

# ====== START ======
bot.run(TOKEN)










