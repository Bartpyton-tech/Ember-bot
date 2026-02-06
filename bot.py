import discord
from discord import app_commands
from discord.ext import commands
import os, json, logging, threading
from dotenv import load_dotenv
from flask import Flask

# ================= LOGI =================
logging.basicConfig(level=logging.INFO)

# ================= ENV ==================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
ROLLBACK_CATEGORY_NAME = os.getenv("ROLLBACK_CATEGORY_NAME", "Rollbacks")

# ================= BOT ==================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ================= FLASK (Render) =======
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot działa"

def run_web():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_web).start()

# ================= DANE =================
DATA_DIR = "data"
DATA_FILE = f"{DATA_DIR}/captures.json"

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
        json.dump(data, f, indent=2, ensure_ascii=False)

# ================= READY =================
@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    logging.info(f"Zalogowano jako {bot.user}")

# ==================================================
# ================== CAPTURES =======================
# ==================================================
def build_embed(capt):
    sklad = capt["sklad"]
    rezerwa = capt["rezerwa"]

    def fmt(lst):
        return "\n".join(f"<@{u}>" for u in lst) if lst else "—"

    return discord.Embed(
        title="🚨 CAPT",
        description=(
            f"👨‍👩‍👧 **Rodzina:** {capt['rodzina']}\n"
            f"🕒 **Godzina:** {capt['godzina']}\n"
            f"📍 **Kwadrat:** {capt['kwadrat']}\n\n"
            f"🟢 **SKŁAD (max 25):**\n{fmt(sklad)}\n\n"
            f"🟡 **REZERWA:**\n{fmt(rezerwa)}"
        ),
        color=0x7B3FE4
    )

class CapturesView(discord.ui.View):
    def __init__(self, capt_id):
        super().__init__(timeout=None)
        self.capt_id = capt_id

    async def refresh(self, interaction):
        data = load_data()
        capt = data["captures"][self.capt_id]
        await interaction.message.edit(embed=build_embed(capt), view=self)

    @discord.ui.button(label="✅ Zapisz się", style=discord.ButtonStyle.success)
    async def zapisz(self, interaction: discord.Interaction, _):
        data = load_data()
        capt = data["captures"][self.capt_id]
        uid = interaction.user.id

        if uid in capt["sklad"] or uid in capt["rezerwa"]:
            return await interaction.response.send_message("❌ Już jesteś zapisany.", ephemeral=True)

        capt["rezerwa"].append(uid)
        save_data(data)
        await interaction.response.send_message("✅ Zapisano na rezerwę.", ephemeral=True)
        await self.refresh(interaction)

    @discord.ui.button(label="❌ Wypisz się", style=discord.ButtonStyle.danger)
    async def wypisz(self, interaction: discord.Interaction, _):
        data = load_data()
        capt = data["captures"][self.capt_id]
        uid = interaction.user.id

        if uid in capt["sklad"]:
            capt["sklad"].remove(uid)
        elif uid in capt["rezerwa"]:
            capt["rezerwa"].remove(uid)
        else:
            return await interaction.response.send_message("❌ Nie jesteś zapisany.", ephemeral=True)

        save_data(data)
        await interaction.response.send_message("✅ Wypisano.", ephemeral=True)
        await self.refresh(interaction)

    @discord.ui.button(label="👥 Wybierz skład", style=discord.ButtonStyle.primary)
    async def wybierz(self, interaction: discord.Interaction, _):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Tylko admin.", ephemeral=True)

        data = load_data()
        capt = data["captures"][self.capt_id]

        all_users = capt["sklad"] + capt["rezerwa"]
        if not all_users:
            return await interaction.response.send_message("Brak zapisanych.", ephemeral=True)

        options = [
            discord.SelectOption(label=interaction.guild.get_member(u).display_name, value=str(u))
            for u in all_users if interaction.guild.get_member(u)
        ]

        select = discord.ui.Select(
            placeholder="Wybierz MAX 25 do składu",
            options=options,
            max_values=min(25, len(options))
        )

        async def select_callback(i):
            capt["sklad"] = [int(v) for v in select.values]
            capt["rezerwa"] = [u for u in all_users if u not in capt["sklad"]]
            save_data(data)
            await i.response.edit_message(content="✅ Skład wybrany.", view=None)
            await self.refresh(interaction)

        select.callback = select_callback
        v = discord.ui.View()
        v.add_item(select)
        await interaction.response.send_message("👥 Wybór składu:", view=v, ephemeral=True)

# ================= KOMENDA =================
@tree.command(name="captures", description="Tworzy capt", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    rodzina="Rodzina",
    godzina="Godzina",
    kwadrat="Kwadrat"
)
async def captures(interaction: discord.Interaction, rodzina: str, godzina: str, kwadrat: str):
    await interaction.response.defer()

    data = load_data()
    capt_id = f"{interaction.id}"

    data["captures"][capt_id] = {
        "rodzina": rodzina,
        "godzina": godzina,
        "kwadrat": kwadrat,
        "sklad": [],
        "rezerwa": []
    }
    save_data(data)

    await interaction.followup.send(
        embed=build_embed(data["captures"][capt_id]),
        view=CapturesView(capt_id)
    )

# ==================================================
# ================= ROLLBACK ========================
# ==================================================
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

        await interaction.response.send_message(f"✅ Utworzono {channel.mention}", ephemeral=True)

@tree.command(name="rollbackstworz", description="Tworzy rollback", guild=discord.Object(id=GUILD_ID))
async def rollbackstworz(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔧 Rollback",
        description="Kliknij przycisk aby utworzyć prywatny kanał.",
        color=0x7B3FE4
    )
    await interaction.response.send_message(embed=embed, view=RollbackView())

# ================= START ==================
bot.run(TOKEN)











