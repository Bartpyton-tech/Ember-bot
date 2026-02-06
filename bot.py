import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import logging
from dotenv import load_dotenv
from flask import Flask
import threading

# ================== LOGI ==================
logging.basicConfig(level=logging.INFO)

# ================== ENV ==================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
ROLLBACK_CATEGORY_NAME = os.getenv("ROLLBACK_CATEGORY_NAME", "Rollbacks")

# ================== BOT ==================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ================== FLASK (RENDER) ==================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot działa"

def run_web():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_web, daemon=True).start()

# ================== DANE ==================
DATA_DIR = "data"
DATA_FILE = f"{DATA_DIR}/captures.json"

def ensure_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"captures": {}}, f)

def load_data():
    ensure_data()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    ensure_data()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ================== READY ==================
@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    logging.info(f"Zalogowano jako {bot.user}")

# =====================================================
# ===================== CAPTURES ======================
# =====================================================
MAX_MAIN = 25

def build_embed(capt):
    main = capt["main"]
    reserve = capt["reserve"]

    def fmt(lst):
        return "\n".join(f"<@{u}>" for u in lst) if lst else "—"

    embed = discord.Embed(
        title="🚨 CAPT",
        description=(
            f"👨‍👩‍👧 **Rodzina:** {capt['rodzina']}\n"
            f"🕒 **Godzina:** {capt['godzina']}\n"
            f"📍 **Kwadrat:** {capt['kwadrat']}\n\n"
            f"🟢 **Skład główny ({len(main)}/{MAX_MAIN})**\n{fmt(main)}\n\n"
            f"🟡 **Rezerwa ({len(reserve)})**\n{fmt(reserve)}"
        ),
        color=0x7B3FE4
    )
    return embed

class CapturesView(discord.ui.View):
    def __init__(self, capt_id):
        super().__init__(timeout=None)
        self.capt_id = capt_id

    async def update(self, interaction):
        data = load_data()
        capt = data["captures"][self.capt_id]
        await interaction.message.edit(embed=build_embed(capt), view=self)

    @discord.ui.button(label="🟢 Skład", style=discord.ButtonStyle.success)
    async def join_main(self, interaction: discord.Interaction, _):
        data = load_data()
        capt = data["captures"][self.capt_id]

        if interaction.user.id in capt["main"]:
            await interaction.response.send_message("❌ Już jesteś w składzie.", ephemeral=True)
            return

        if len(capt["main"]) >= MAX_MAIN:
            await interaction.response.send_message("❌ Skład pełny.", ephemeral=True)
            return

        if interaction.user.id in capt["reserve"]:
            capt["reserve"].remove(interaction.user.id)

        capt["main"].append(interaction.user.id)
        save_data(data)
        await interaction.response.defer()
        await self.update(interaction)

    @discord.ui.button(label="🟡 Rezerwa", style=discord.ButtonStyle.secondary)
    async def join_reserve(self, interaction: discord.Interaction, _):
        data = load_data()
        capt = data["captures"][self.capt_id]

        if interaction.user.id in capt["reserve"]:
            await interaction.response.send_message("❌ Już jesteś w rezerwie.", ephemeral=True)
            return

        if interaction.user.id in capt["main"]:
            capt["main"].remove(interaction.user.id)

        capt["reserve"].append(interaction.user.id)
        save_data(data)
        await interaction.response.defer()
        await self.update(interaction)

    @discord.ui.button(label="❌ Wypisz", style=discord.ButtonStyle.danger)
    async def leave(self, interaction: discord.Interaction, _):
        data = load_data()
        capt = data["captures"][self.capt_id]

        if interaction.user.id in capt["main"]:
            capt["main"].remove(interaction.user.id)
        elif interaction.user.id in capt["reserve"]:
            capt["reserve"].remove(interaction.user.id)
        else:
            await interaction.response.send_message("❌ Nie jesteś zapisany.", ephemeral=True)
            return

        save_data(data)
        await interaction.response.defer()
        await self.update(interaction)

@tree.command(name="captures", description="Tworzy capt z wyborem składu", guild=discord.Object(id=GUILD_ID))
async def captures(interaction: discord.Interaction, rodzina: str, godzina: str, kwadrat: str):
    data = load_data()
    capt_id = f"{rodzina}-{godzina}-{kwadrat}"

    data["captures"][capt_id] = {
        "rodzina": rodzina,
        "godzina": godzina,
        "kwadrat": kwadrat,
        "main": [],
        "reserve": []
    }

    save_data(data)

    await interaction.response.send_message(
        embed=build_embed(data["captures"][capt_id]),
        view=CapturesView(capt_id)
    )

# =====================================================
# ===================== ROLLBACK ======================
# =====================================================
class RollbackView(discord.ui.View):
    @discord.ui.button(label="🛠 Utwórz kanał", style=discord.ButtonStyle.primary)
    async def create(self, interaction: discord.Interaction, _):
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
    await interaction.response.send_message(embed=embed, view=RollbackView())

# ================== START ==================
bot.run(TOKEN)











