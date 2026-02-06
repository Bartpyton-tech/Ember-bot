import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import logging
from dotenv import load_dotenv
from flask import Flask
import threading

# ===== LOGI =====
logging.basicConfig(level=logging.INFO)

# ===== ENV =====
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
ROLLBACK_CATEGORY_NAME = os.getenv("ROLLBACK_CATEGORY_NAME", "Rollbacks")

# ===== BOT =====
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ===== FLASK (Render) =====
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot działa"

def run_web():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_web).start()

# ===== DANE =====
DATA_FILE = "data/captures.json"

def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ===== READY =====
@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    logging.info(f"Zalogowano jako {bot.user}")

# =====================================================
# ==================== CAPTURES =======================
# =====================================================

MAX_SKLAD = 25

def build_embed(capt):
    sklad = capt["sklad"]
    rezerwa = capt["rezerwa"]

    sklad_txt = "\n".join(
        f"{i+1}. <@{uid}>" for i, uid in enumerate(sklad)
    ) if sklad else "—"

    rezerwa_txt = "\n".join(
        f"{i+1}. <@{uid}>" for i, uid in enumerate(rezerwa)
    ) if rezerwa else "—"

    embed = discord.Embed(
        title="🚨 CAPT",
        color=0x7B3FE4
    )
    embed.add_field(
        name=f"🟢 Skład ({len(sklad)}/{MAX_SKLAD})",
        value=sklad_txt,
        inline=False
    )
    embed.add_field(
        name="🟡 Rezerwa",
        value=rezerwa_txt,
        inline=False
    )
    return embed

class CapturesView(discord.ui.View):
    def __init__(self, capt_id):
        super().__init__(timeout=None)
        self.capt_id = capt_id

    async def refresh(self, interaction):
        data = load_data()
        capt = data["captures"][self.capt_id]
        embed = build_embed(capt)
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="🟢 Do składu", style=discord.ButtonStyle.success)
    async def sklad(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        capt = data["captures"][self.capt_id]
        uid = interaction.user.id

        if uid in capt["sklad"] or uid in capt["rezerwa"]:
            await interaction.response.send_message("❌ Już jesteś zapisany.", ephemeral=True)
            return

        if len(capt["sklad"]) < MAX_SKLAD:
            capt["sklad"].append(uid)
            msg = "✅ Dodano do składu."
        else:
            capt["rezerwa"].append(uid)
            msg = "⚠️ Skład pełny – dodano do rezerwy."

        save_data(data)
        await interaction.response.send_message(msg, ephemeral=True)
        await self.refresh(interaction)

    @discord.ui.button(label="🟡 Do rezerwy", style=discord.ButtonStyle.secondary)
    async def rezerwa(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        capt = data["captures"][self.capt_id]
        uid = interaction.user.id

        if uid in capt["sklad"] or uid in capt["rezerwa"]:
            await interaction.response.send_message("❌ Już jesteś zapisany.", ephemeral=True)
            return

        capt["rezerwa"].append(uid)
        save_data(data)
        await interaction.response.send_message("✅ Dodano do rezerwy.", ephemeral=True)
        await self.refresh(interaction)

    @discord.ui.button(label="❌ Wypisz się", style=discord.ButtonStyle.danger)
    async def wypisz(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        capt = data["captures"][self.capt_id]
        uid = interaction.user.id

        if uid in capt["sklad"]:
            capt["sklad"].remove(uid)
        elif uid in capt["rezerwa"]:
            capt["rezerwa"].remove(uid)
        else:
            await interaction.response.send_message("❌ Nie jesteś zapisany.", ephemeral=True)
            return

        save_data(data)
        await interaction.response.send_message("✅ Wypisano.", ephemeral=True)
        await self.refresh(interaction)

# ===== KOMENDA /captures =====
@tree.command(
    name="captures",
    description="Tworzy capt z wyborem składu",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    rodzina="Nazwa rodziny",
    godzina="Godzina (np. 20:00)",
    kwadrat="Kwadrat (np. G5)"
)
async def captures(interaction: discord.Interaction, rodzina: str, godzina: str, kwadrat: str):
    data = load_data()
    capt_id = f"{rodzina}-{godzina}-{kwadrat}"

    data["captures"][capt_id] = {
        "rodzina": rodzina,
        "godzina": godzina,
        "kwadrat": kwadrat,
        "sklad": [],
        "rezerwa": []
    }
    save_data(data)

    embed = build_embed(data["captures"][capt_id])

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

@tree.command(
    name="rollbackstworz",
    description="Tworzy rollback",
    guild=discord.Object(id=GUILD_ID)
)
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

# ===== START =====
bot.run(TOKEN)











