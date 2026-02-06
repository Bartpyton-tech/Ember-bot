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
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ===== FLASK (Render keep-alive) =====
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot działa"

def run_web():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_web, daemon=True).start()

# ===== DANE =====
DATA_DIR = "data"
DATA_FILE = "data/captures.json"

def ensure_data():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
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
        json.dump(data, f, indent=2)

# ===== READY =====
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    logging.info(f"Zalogowano jako {bot.user}")

# =====================================================
# ===================== CAPTURES ======================
# =====================================================

def build_embed(capt):
    sklad = capt["sklad"]
    rezerwa = capt["rezerwa"]

    def fmt(users):
        return "\n".join(f"<@{u}>" for u in users) if users else "—"

    embed = discord.Embed(
        title="🚨 CAPT",
        description=(
            f"👨‍👩‍👧 **Rodzina:** {capt['rodzina']}\n"
            f"🕒 **Godzina:** {capt['godzina']}\n"
            f"📍 **Kwadrat:** {capt['kwadrat']}\n\n"
            f"🟢 **Skład ({len(sklad)}/25):**\n{fmt(sklad)}\n\n"
            f"🟡 **Rezerwa:**\n{fmt(rezerwa)}"
        ),
        color=0x7B3FE4
    )
    return embed

class SelectView(discord.ui.View):
    def __init__(self, capt_id, users, role):
        super().__init__(timeout=60)
        self.capt_id = capt_id
        self.users = users
        self.role = role

        options = [
            discord.SelectOption(
                label=str(i+1),
                description=f"Użytkownik {uid}",
                value=str(uid)
            ) for i, uid in enumerate(users[:25])
        ]

        self.select = discord.ui.Select(
            placeholder="Wybierz osoby",
            min_values=1,
            max_values=len(options),
            options=options
        )
        self.select.callback = self.callback
        self.add_item(self.select)

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        capt = data["captures"][self.capt_id]

        for uid in self.select.values:
            uid = int(uid)
            if self.role == "sklad" and uid not in capt["sklad"]:
                if len(capt["sklad"]) < 25:
                    capt["sklad"].append(uid)
                    if uid in capt["rezerwa"]:
                        capt["rezerwa"].remove(uid)
            elif self.role == "rezerwa" and uid not in capt["rezerwa"]:
                capt["rezerwa"].append(uid)
                if uid in capt["sklad"]:
                    capt["sklad"].remove(uid)

        save_data(data)
        await interaction.response.send_message("✅ Zaktualizowano", ephemeral=True)

class CapturesView(discord.ui.View):
    def __init__(self, capt_id):
        super().__init__(timeout=None)
        self.capt_id = capt_id

    @discord.ui.button(label="✅ Zapisz się", style=discord.ButtonStyle.success)
    async def zapisz(self, interaction: discord.Interaction, _):
        data = load_data()
        capt = data["captures"][self.capt_id]
        uid = interaction.user.id

        if uid in capt["users"]:
            await interaction.response.send_message("Już zapisany", ephemeral=True)
            return

        capt["users"].append(uid)
        save_data(data)

        await interaction.message.edit(embed=build_embed(capt), view=self)
        await interaction.response.send_message("Zapisano", ephemeral=True)

    @discord.ui.button(label="❌ Wypisz się", style=discord.ButtonStyle.danger)
    async def wypisz(self, interaction: discord.Interaction, _):
        data = load_data()
        capt = data["captures"][self.capt_id]
        uid = interaction.user.id

        for lst in ["users", "sklad", "rezerwa"]:
            if uid in capt[lst]:
                capt[lst].remove(uid)

        save_data(data)
        await interaction.message.edit(embed=build_embed(capt), view=self)
        await interaction.response.send_message("Wypisano", ephemeral=True)

    @discord.ui.button(label="🎯 Wybierz skład", style=discord.ButtonStyle.primary)
    async def wybierz(self, interaction: discord.Interaction, _):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Brak uprawnień", ephemeral=True)
            return

        data = load_data()
        capt = data["captures"][self.capt_id]

        await interaction.response.send_message(
            "Najpierw **SKŁAD**, potem **REZERWA**",
            view=SelectView(self.capt_id, capt["users"], "sklad"),
            ephemeral=True
        )

@tree.command(name="captures", description="Tworzy capt", guild=discord.Object(id=GUILD_ID))
async def captures(interaction: discord.Interaction, rodzina: str, godzina: str, kwadrat: str):
    data = load_data()
    capt_id = f"{interaction.id}"

    data["captures"][capt_id] = {
        "rodzina": rodzina,
        "godzina": godzina,
        "kwadrat": kwadrat,
        "users": [],
        "sklad": [],
        "rezerwa": []
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
            interaction.user: discord.PermissionOverwrite(view_channel=True)
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
            f"Utworzono {channel.mention}",
            ephemeral=True
        )

@tree.command(name="rollbackstworz", description="Tworzy rollback", guild=discord.Object(id=GUILD_ID))
async def rollbackstworz(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=discord.Embed(
            title="🔧 Rollback",
            description="Kliknij przycisk aby utworzyć kanał",
            color=0x7B3FE4
        ),
        view=RollbackView()
    )

# ===== START =====
bot.run(TOKEN)










