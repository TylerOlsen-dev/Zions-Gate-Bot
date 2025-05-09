import discord
from discord.ext import commands
import aiohttp
import asyncio
import csv
import os
from datetime import datetime, UTC
from typing import Optional
from dotenv import load_dotenv
import csv
from pathlib import Path
from typing import List, Dict, Any
from git import Repo
load_dotenv()

BASE_DIR = Path(__file__).parent
SERVERS_CSV = BASE_DIR / "servers.csv"
USERS_CSV = BASE_DIR / "users.csv"

# === Git snapshot settings ===
GIT_TOKEN = os.getenv("CSV_PUSH_TOKEN")
REPO_PATH = BASE_DIR
CSV_FILES = ["servers.csv", "users.csv"]

def push_csv_snapshot():
    """Stage CSVs, amend moving snapshot commit, force-push."""
    if not GIT_TOKEN:
        return 
    try:
        repo = Repo(REPO_PATH, search_parent_directories=True)
        repo_root = Path(repo.working_tree_dir)             
        rel_files = [str(SERVERS_CSV.relative_to(repo_root)), 
                     str(USERS_CSV.relative_to(repo_root))]
        repo.index.add(rel_files)
        commit_msg = f"CSV snapshot {datetime.now(UTC):%Y-%m-%d %H:%M UTC}"

        if repo.head.is_valid():
            repo.git.commit("--amend", "--no-edit", "-m", commit_msg)
        else:
            repo.index.commit(commit_msg)
        origin = repo.remote(name="origin")
        origin.set_url(f"https://{GIT_TOKEN}@github.com/TylerOlsen-dev/zions-gate-bot.git")
        origin.push(force=True)
    except Exception as e:
        print(f"[CSV snapshot] Git push skipped: {e}")


SERVERS_COLUMNS = ["Server_AI_ID","Guild_ID","Server_Name","Local_1","Local_2","Local_3","Global_1","Global_2","Global_3","OwnerID","setup"]
USERS_COLUMNS = ["User_AI_ID","User_ID","User_Name","Account_Age","Global_Banned"]

def _load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, newline='', encoding="utf-8") as f:
        return list(csv.DictReader(f))

def _save_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]):
    with open(path, "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        push_csv_snapshot()

def _next_id(rows: List[Dict[str, Any]], id_field: str) -> int:
    if not rows:
        return 1
    max_id = max(int(r[id_field]) for r in rows if r.get(id_field, "").isdigit())
    return max_id + 1

class CSVCursor:
    def __init__(self):
        self._results = []
    
    def execute(self, query: str, params: tuple = ()):
        query_upper = query.upper()
        if query_upper.startswith("SELECT"):
            self._handle_select(query_upper, params)
        elif query_upper.startswith("INSERT INTO SERVERS"):
            self._handle_insert_servers(params)
        elif query_upper.startswith("INSERT INTO USERS"):
            self._handle_insert_users(params)
        elif query_upper.startswith("UPDATE USERS"):
            self._handle_update_users(params)
        elif query_upper.startswith("UPDATE SERVERS"):
            self._handle_update_servers(params)
        else:
            raise NotImplementedError(f"Query not supported: {query}")
    
    def _handle_select(self, query_upper: str, params: tuple):
        if "FROM SERVERS" in query_upper:
            servers = _load_csv(SERVERS_CSV)
            guild_id = str(params[0])
            if "SELECT GUILD_ID" in query_upper:
                row = next((r for r in servers if r["Guild_ID"] == guild_id), None)
                self._results = [(row["Guild_ID"],)] if row else []
            elif "SELECT SETUP" in query_upper:
                row = next((r for r in servers if r["Guild_ID"] == guild_id), None)
                self._results = [(row["setup"],)] if row else []
            elif "GLOBAL_1" in query_upper:
                row = next((r for r in servers if r["Guild_ID"] == guild_id), None)
                if row:
                    self._results = [(row["Global_1"], row["Global_2"], row["Global_3"])]
                else:
                    self._results = []
            elif "LOCAL_1" in query_upper:
                row = next((r for r in servers if r["Guild_ID"] == guild_id), None)
                if row:
                    self._results = [(row["Local_1"], row["Local_2"], row["Local_3"])]
                else:
                    self._results = []
            elif "OWNERID" in query_upper:
                row = next((r for r in servers if r["Guild_ID"] == guild_id), None)
                self._results = [(row["OwnerID"],)] if row else []
            else:
                self._results = []
        elif "FROM USERS" in query_upper:
            users = _load_csv(USERS_CSV)
            user_id = str(params[0])
            if "SELECT USER_ID" in query_upper:
                row = next((r for r in users if r["User_ID"] == user_id), None)
                self._results = [(row["User_ID"],)] if row else []
            elif "SELECT GLOBAL_BANNED" in query_upper:
                row = next((r for r in users if r["User_ID"] == user_id), None)
                self._results = [(row["Global_Banned"],)] if row else []
            else:
                self._results = []
        else:
            self._results = []
    
    def _handle_insert_servers(self, params: tuple):
        servers = _load_csv(SERVERS_CSV)
        new_id = str(_next_id(servers, "Server_AI_ID"))
        guild_id, server_name = str(params[0]), params[1]
        new_row = dict.fromkeys(SERVERS_COLUMNS, "")
        new_row.update({
            "Server_AI_ID": new_id,
            "Guild_ID": guild_id,
            "Server_Name": server_name,
            "OwnerID": "0",
            "setup": "False",
        })
        servers.append(new_row)
        _save_csv(SERVERS_CSV, servers, SERVERS_COLUMNS)
        self._results = []
    
    def _handle_insert_users(self, params: tuple):
        users = _load_csv(USERS_CSV)
        new_id = str(_next_id(users, "User_AI_ID"))
        user_id, user_name, account_age, global_banned = params
        new_row = dict.fromkeys(USERS_COLUMNS, "")
        new_row.update({
            "User_AI_ID": new_id,
            "User_ID": str(user_id),
            "User_Name": user_name,
            "Account_Age": account_age,
            "Global_Banned": str(global_banned),
        })
        users.append(new_row)
        _save_csv(USERS_CSV, users, USERS_COLUMNS)
        self._results = []
    
    def _handle_update_users(self, params: tuple):
        global_banned, user_id = params
        users = _load_csv(USERS_CSV)
        for row in users:
            if row["User_ID"] == str(user_id):
                row["Global_Banned"] = str(global_banned)
                break
        _save_csv(USERS_CSV, users, USERS_COLUMNS)
        self._results = []
    
    def _handle_update_servers(self, params: tuple):
        (server_name, local1, local2, local3, global1, global2, global3, guild_id) = params
        servers = _load_csv(SERVERS_CSV)
        for row in servers:
            if row["Guild_ID"] == str(guild_id):
                row.update({
                    "Server_Name": server_name,
                    "Local_1": str(local1) if local1 else "",
                    "Local_2": str(local2) if local2 else "",
                    "Local_3": str(local3) if local3 else "",
                    "Global_1": str(global1) if global1 else "",
                    "Global_2": str(global2) if global2 else "",
                    "Global_3": str(global3) if global3 else "",
                    "setup": "True",
                })
                break
        _save_csv(SERVERS_CSV, servers, SERVERS_COLUMNS)
        self._results = []
    
    def fetchone(self):
        return self._results[0] if self._results else None
    
    def fetchall(self):
        return self._results
    
    def close(self):
        pass

class CSVConnection:
    def cursor(self):
        return CSVCursor()
    def commit(self):
        pass
    def close(self):
        pass

def db_connection():
    return CSVConnection()


def _is_truthy(val):
    return str(val).strip().lower() in ("1", "true", "yes")


BAN_WEBHOOK_URL = os.getenv("BAN_WEBHOOK_URL")
AVATAR_WEBHOOK_URL = os.getenv("AVATAR_WEBHOOK_URL")
REPORT_WEBHOOK_URL = os.getenv("REPORT_WEBHOOK_URL")
LK_WEBHOOK_URL = os.getenv("LK_WEBHOOK_URL")
LB_WEBHOOK_URL = os.getenv("LB_WEBHOOK_URL")
PURGE_WEBHOOK_URL = os.getenv("PURGE_WEBHOOK_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_user_display(user) -> str:
    try:
        name = user.name
    except AttributeError:
        name = "Deleted User"
    try:
        disc = user.discriminator
    except AttributeError:
        disc = "0000"
    return f"{name}#{disc}"

# Server Registration
async def register_server(guild: discord.Guild):
    try:
        connection = db_connection()
        cursor = connection.cursor()
        query = "SELECT Guild_ID FROM servers WHERE Guild_ID = %s"
        cursor.execute(query, (guild.id,))
        result = cursor.fetchone()
        if result is None:
            insert_query = "INSERT INTO servers (Guild_ID, Server_Name, OwnerID, setup) VALUES (%s, %s, 0, FALSE)"
            cursor.execute(insert_query, (guild.id, guild.name))
            connection.commit()
            print(f"Registered server: {guild.name} (ID: {guild.id})")
        cursor.close()
        connection.close()
    except Exception as e:
        print("Error registering server:", e)

# Global Check for Server Setup
async def check_server_setup(interaction: discord.Interaction) -> bool:
    if interaction.command and interaction.command.name == "setup":
        return True
    guild = interaction.guild
    if guild is None:
        return True
    try:
        connection = db_connection()
        cursor = connection.cursor()
        query = "SELECT setup FROM servers WHERE Guild_ID = %s"
        cursor.execute(query, (guild.id,))
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        if result and _is_truthy(result[0]):
            return True
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message("Access Denied: This server needs to be set up first. Run /setup", ephemeral=True)
            else:
                await interaction.followup.send("Access Denied: This server needs to be set up first. Run /setup", ephemeral=True)
            return False
    except Exception as e:
        print("Error checking server setup:", e)
        if not interaction.response.is_done():
            await interaction.response.send_message("Server setup check failed. Run /setup", ephemeral=True)
        else:
            await interaction.followup.send("Server setup check failed. Run /setup", ephemeral=True)
        return False

# Command Role Check
async def check_command_roles(interaction: discord.Interaction) -> bool:
    restricted_commands = {"localkick", "localban", "globalban", "globalunban"}
    if interaction.command is None:
        return True
    command_name = interaction.command.name.lower()
    if command_name not in restricted_commands:
        return True
    guild = interaction.guild
    if guild is None:
        return True

    allowed_roles_raw = []
    try:
        connection = db_connection()
        cursor = connection.cursor()
        if command_name in ("globalban", "globalunban"):
            cursor.execute("SELECT Global_1, Global_2, Global_3 FROM servers WHERE Guild_ID = %s", (guild.id,))
            result = cursor.fetchone()
            allowed_roles_raw = list(result) if result else []
        elif command_name in ("localkick", "localban"):
            cursor.execute("SELECT Local_1, Local_2, Local_3 FROM servers WHERE Guild_ID = %s", (guild.id,))
            local_result = cursor.fetchone()
            local_roles = list(local_result) if local_result else []
            cursor.execute("SELECT Global_1, Global_2, Global_3 FROM servers WHERE Guild_ID = %s", (guild.id,))
            global_result = cursor.fetchone()
            global_roles = list(global_result) if global_result else []
            allowed_roles_raw = local_roles + global_roles
        cursor.close()
        connection.close()
    except Exception as e:
        print("Error retrieving command roles:", e)
        raise discord.app_commands.CheckFailure("Access Denied: Could not verify your permissions.")

    # Clean and convert role IDs
    allowed_roles = []
    for role in allowed_roles_raw:
        if role and str(role).upper() != "NULL":
            try:
                allowed_roles.append(int(role))
            except (ValueError, TypeError):
                continue

    user_role_ids = [role.id for role in interaction.user.roles]
    if any(r in user_role_ids for r in allowed_roles):
        return True
    else:
        raise discord.app_commands.CheckFailure("Access Denied: You do not have permission to use this command.")

# Combined Global Check
async def combined_check(interaction: discord.Interaction) -> bool:
    try:
        if not await check_server_setup(interaction):
            return False
        if not await check_command_roles(interaction):
            return False
        return True
    except discord.app_commands.CheckFailure as e:
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(str(e), ephemeral=True)
            else:
                await interaction.followup.send(str(e), ephemeral=True)
        except Exception as ex:
            print("Error sending combined check error message:", ex)
        return False

bot.tree.interaction_check = combined_check

# Global Error Handler
@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CheckFailure):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(str(error), ephemeral=True)
            else:
                await interaction.followup.send(str(error), ephemeral=True)
        except Exception as e:
            print("Error sending error message:", e)
    else:
        print("Unhandled error:", error)
        if not interaction.response.is_done():
            await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)

# Database Utility Functions
async def add_member_to_users(member: discord.Member):
    if member.bot:
        return
    user_id = member.id
    user_name = get_user_display(member)
    account_age = member.created_at.strftime('%Y-%m-%d')
    try:
        connection = db_connection()
        cursor = connection.cursor()
        select_query = "SELECT User_ID FROM Users WHERE User_ID = %s"
        cursor.execute(select_query, (user_id,))
        result = cursor.fetchone()
        if result is None:
            insert_query = "INSERT INTO Users (User_ID, User_Name, Account_Age, Global_Banned) VALUES (%s, %s, %s, %s)"
            data_tuple = (user_id, user_name, account_age, "False")
            cursor.execute(insert_query, data_tuple)
            connection.commit()
            print(f"Added new user: {user_name} (ID: {user_id}) to Users table.")
        cursor.close()
        connection.close()
    except Exception as e:
        print("Database error:", e)

async def add_user_to_db(user: discord.User):
    user_id = user.id
    user_name = get_user_display(user)
    account_age = user.created_at.strftime('%Y-%m-%d')
    try:
        connection = db_connection()
        cursor = connection.cursor()
        select_query = "SELECT User_ID FROM Users WHERE User_ID = %s"
        cursor.execute(select_query, (user_id,))
        result = cursor.fetchone()
        if result is None:
            insert_query = "INSERT INTO Users (User_ID, User_Name, Account_Age, Global_Banned) VALUES (%s, %s, %s, %s)"
            data_tuple = (user_id, user_name, account_age, "False")
            cursor.execute(insert_query, data_tuple)
            connection.commit()
            print(f"Added new user: {user_name} (ID: {user_id}) to Users table.")
        cursor.close()
        connection.close()
    except Exception as e:
        print("Database error:", e)

async def set_global_ban(user_id: int, banned: bool):
    try:
        connection = db_connection()
        cursor = connection.cursor()
        query = "UPDATE Users SET Global_Banned = %s WHERE User_ID = %s"
        value = "True" if banned else "False"
        cursor.execute(query, (value, user_id))
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as e:
        print("Database error:", e)

async def is_globally_banned(user_id: int) -> bool:
    try:
        connection = db_connection()
        cursor = connection.cursor()
        query = "SELECT Global_Banned FROM Users WHERE User_ID = %s"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        return result and _is_truthy(result[0])
    except Exception as e:
        print("Database error:", e)
        return False

# On Member Join
@bot.event
async def on_member_join(member: discord.Member):
    try:
        connection = db_connection()
        cursor = connection.cursor()
        query = "SELECT setup FROM servers WHERE Guild_ID = %s"
        cursor.execute(query, (member.guild.id,))
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        if result and _is_truthy(result[0]):
            await add_member_to_users(member)
            if await is_globally_banned(member.id):
                try:
                    await member.guild.ban(member, reason="Global ban active.")
                    print(f"Banned {member} from {member.guild.name} due to global ban.")
                except Exception as e:
                    print(f"Error banning {member} in {member.guild.name}: {e}")
        else:
            print(f"Server {member.guild.name} is not set up; not adding {member} to Users table.")
    except Exception as e:
        print("Error checking server setup on member join:", e)

# Slash Command: Setup
@bot.tree.command(name="setup", description="Configure this server's command access. (Owner only)")
@discord.app_commands.describe(
    local1="Primary local role (required)",
    global1="Primary global role (required)",
    local2="Optional local role #2",
    local3="Optional local role #3",
    global2="Optional global role #2",
    global3="Optional global role #3"
)
async def setup(interaction: discord.Interaction, local1: discord.Role, global1: discord.Role, local2: Optional[discord.Role] = None, local3: Optional[discord.Role] = None, global2: Optional[discord.Role] = None, global3: Optional[discord.Role] = None):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
        return
    try:
        await register_server(guild)
    except Exception as e:
        print("Error registering server in /setup:", e)
    try:
        connection = db_connection()
        cursor = connection.cursor()
        query = "SELECT OwnerID FROM servers WHERE Guild_ID = %s"
        cursor.execute(query, (guild.id,))
        result = cursor.fetchone()
        cursor.close()
        connection.close()
    except Exception as e:
        print("Error retrieving OwnerID:", e)
        await interaction.response.send_message("Error checking server registration.", ephemeral=True)
        return
    if result is None or int(result[0]) == 0:
        await interaction.response.send_message("Access Denied: Server owner not registered. Please contact the bot admin.", ephemeral=True)
        return
    if interaction.user.id != int(result[0]):
        await interaction.response.send_message("Access Denied: Only the registered server owner can run this command.", ephemeral=True)
        return
    try:
        connection = db_connection()
        cursor = connection.cursor()
        update_query = "UPDATE servers SET Server_Name = %s, Local_1 = %s, Local_2 = %s, Local_3 = %s, Global_1 = %s, Global_2 = %s, Global_3 = %s, setup = TRUE WHERE Guild_ID = %s"
        data = (guild.name, local1.id, local2.id if local2 else None, local3.id if local3 else None, global1.id, global2.id if global2 else None, global3.id if global3 else None, guild.id)
        cursor.execute(update_query, data)
        connection.commit()
        cursor.close()
        connection.close()
        for member in guild.members:
            await add_member_to_users(member)
        await interaction.response.send_message("Server setup complete. Command access is now enabled.", ephemeral=True)
    except Exception as e:
        print("Error in /setup:", e)
        await interaction.response.send_message("There was an error during setup.", ephemeral=True)

# Slash Command: Global Ban
@bot.tree.command(name="globalban", description="Globally ban a user from all servers. Reason required; reply with evidence screenshots.")
async def globalban(interaction: discord.Interaction, user: discord.User, reason: str):
    await interaction.response.defer(ephemeral=True)
    # Ensure the user is in the database
    await add_user_to_db(user)
    await set_global_ban(user.id, True)
    banned_in = []
    for guild in bot.guilds:
        member = guild.get_member(user.id)
        if member is None:
            try:
                # Use the provided user object directly
                try:
                    await guild.ban(user, reason=reason)
                    banned_in.append(guild.name)
                except Exception as e:
                    print(f"Failed to ban <@{user.id}> in {guild.name}: {e}")
            except Exception as e:
                print(f"Error processing user {user.id} in {guild.name}: {e}")
        else:
            await add_member_to_users(member)
            try:
                await guild.ban(member, reason=reason)
                banned_in.append(guild.name)
            except Exception as e:
                print(f"Failed to ban <@{user.id}> in {guild.name}: {e}")
    loc = f"{interaction.guild.name} - {interaction.channel.mention}"
    webhook_message = (
        f"**Global Ban executed for <@{user.id}> (ID: {user.id}).**\n"
        f"**Reason:** {reason}\n"
        f"**Banned by:** <@{interaction.user.id}> (ID: {interaction.user.id})\n"
        f"**Location:** {loc}\n"
        f"**Servers affected:** {', '.join(banned_in)}\n\n"
        "Please reply with screenshots of evidence supporting this ban."
    )
    try:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(BAN_WEBHOOK_URL, session=session)
            await webhook.send(content=webhook_message)
    except Exception as e:
        print("Error sending webhook message in global ban:", e)
    await interaction.followup.send(f"Globally banned <@{user.id}> from: {', '.join(banned_in)}. Database updated.", ephemeral=True)

# Slash Command: Global Unban
@bot.tree.command(name="globalunban", description="Globally unban a user from all servers and remove the global ban flag.")
async def globalunban(interaction: discord.Interaction, user: discord.User):
    await interaction.response.defer(ephemeral=True)
    await set_global_ban(user.id, False)
    unbanned_in = []
    for guild in bot.guilds:
        try:
            await guild.unban(user, reason="Global unban command issued.")
            unbanned_in.append(guild.name)
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"Failed to unban <@{user.id}> in {guild.name}: {e}")
    loc = f"{interaction.guild.name} - {interaction.channel.mention}"
    webhook_message = (
        f"**Global Unban executed for <@{user.id}> (ID: {user.id}).**\n"
        f"**Executed by:** <@{interaction.user.id}> (ID: {interaction.user.id})\n"
        f"**Location:** {loc}\n"
        f"**Guilds affected:** {', '.join(unbanned_in) if unbanned_in else 'None'}."
    )
    try:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(BAN_WEBHOOK_URL, session=session)
            await webhook.send(content=webhook_message)
    except Exception as e:
        print("Error sending webhook message in global unban:", e)
    await interaction.followup.send(f"Global unban executed for <@{user.id}> from: {', '.join(unbanned_in)}. Database updated.", ephemeral=True)

# Slash Command: Report User
@bot.tree.command(name="reportuser", description="Report a user. Specify the user, reason, and location of the incident.")
async def reportuser(interaction: discord.Interaction, user: discord.User, reason: str, location: str):
    report_message = (
        f"**User Report Received**\n\n"
        f"**Reported User:** <@{user.id}> (ID: {user.id})\n"
        f"**Reported By:** <@{interaction.user.id}> (ID: {interaction.user.id})\n"
        f"**Location:** {location}\n"
        f"**Reason:** {reason}"
    )
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(REPORT_WEBHOOK_URL, session=session)
        await webhook.send(content=report_message)
    if not interaction.response.is_done():
        await interaction.response.send_message("Your report has been submitted. Moderators or administrators will review your report and may contact you for further details.", ephemeral=True)
    else:
        await interaction.followup.send("Your report has been submitted. Moderators or administrators will review your report and may contact you for further details.", ephemeral=True)

@bot.tree.command(name="sync", description="Force-refresh slash commands in this server.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def sync_here(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await bot.tree.sync(guild=interaction.guild)
    await interaction.followup.send("Commands synced for this guild.", ephemeral=True)
    
# Slash Command: Local Kick
@bot.tree.command(name="localkick", description="Kick a user from this server. Reason required; reply with evidence screenshots.")
async def localkick(interaction: discord.Interaction, user: discord.Member, reason: str):
    try:
        await interaction.guild.kick(user, reason=reason)
        loc = f"{interaction.guild.name} - {interaction.channel.mention}"
        webhook_message = (
            f"**Local Kick executed for <@{user.id}> (ID: {user.id}) in {interaction.guild.name}.**\n"
            f"**Reason:** {reason}\n"
            f"**Location:** {loc}\n\n"
            "Please reply with screenshots of evidence supporting this kick."
        )
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(LK_WEBHOOK_URL, session=session)
            await webhook.send(content=webhook_message)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Locally kicked <@{user.id}> from {interaction.guild.name}.", ephemeral=True)
        else:
            await interaction.followup.send(f"Locally kicked <@{user.id}> from {interaction.guild.name}.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error kicking user: {e}", ephemeral=True)

# Slash Command: Local Ban
@bot.tree.command(name="localban", description="Ban a user from this server. Reason required; reply with evidence screenshots.")
async def localban(interaction: discord.Interaction, user: discord.Member, reason: str):
    try:
        await interaction.guild.ban(user, reason=reason)
        loc = f"{interaction.guild.name} - {interaction.channel.mention}"
        webhook_message = (
            f"**Local Ban executed for <@{user.id}> (ID: {user.id}) in {interaction.guild.name}.**\n"
            f"**Reason:** {reason}\n"
            f"**Location:** {loc}\n\n"
            "Please reply with screenshots of evidence supporting this ban."
        )
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(LB_WEBHOOK_URL, session=session)
            await webhook.send(content=webhook_message)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Locally banned <@{user.id}> from {interaction.guild.name}.", ephemeral=True)
        else:
            await interaction.followup.send(f"Locally banned <@{user.id}> from {interaction.guild.name}.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error banning user: {e}", ephemeral=True)


@bot.tree.command(
    name="searchuser",
    description="Search users.csv by ID or username (global roles only)."
)
@discord.app_commands.describe(
    query="Discord ID or username"
)
async def searchuser(interaction: discord.Interaction, query: str):
    await interaction.response.defer(ephemeral=True)
    try:
        conn = db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT Global_1, Global_2, Global_3 FROM servers WHERE Guild_ID = %s",
            (interaction.guild.id,)
        )
        allowed_roles = [
            int(r) for r in cur.fetchone() if r and str(r).upper() != "NULL"
        ]
        cur.close()
        conn.close()
    except Exception:
        return await interaction.followup.send(
            "Internal error resolving roles.", ephemeral=True
        )
    if not any(r in [role.id for role in interaction.user.roles] for r in allowed_roles):
        return await interaction.followup.send(
            "Access Denied: You do not have permission to use this command.",
            ephemeral=True,
        )
    matches = []
    try:
        with open(USERS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if query.isdigit() and row["User_ID"] == query:
                    matches.append(row)
                elif not query.isdigit():
                    q_lower = query.lower()
                    stored = row["User_Name"].lower()
                    if ("#" in q_lower and stored == q_lower) or (stored.split("#")[0] == q_lower):
                        matches.append(row)
    except Exception:
        return await interaction.followup.send(
            "Internal error reading database.", ephemeral=True
        )
    if not matches:
        return await interaction.followup.send(
            "No matching users found.", ephemeral=True
        )
    lines = [
        f"User_ID: {r['User_ID']} | User_Name: {r['User_Name']} | "
        f"Account_Age: {r['Account_Age']} | Global_Banned: {r['Global_Banned']}"
        for r in matches[:10]
    ]
    await interaction.followup.send("\n".join(lines), ephemeral=True)



# Slash Command: Purge
@bot.tree.command(name="purge", description="Delete messages and log them.")
@discord.app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, channel: discord.TextChannel, limit: int):
    if limit <= 0 or limit > 1000:
        await interaction.response.send_message("Please specify a limit between 1 and 1000.", ephemeral=True)
        return
    await interaction.response.send_message(f"Purging {limit} messages from {channel.mention}.", ephemeral=True)
    deleted_messages = await channel.purge(limit=limit)
    log_filename = f"purged_messages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(log_filename, mode="w", encoding="utf-8", newline="") as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["Timestamp", "Author", "Author ID", "Content"])
        for message in deleted_messages:
            csvwriter.writerow([
                message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                f"{message.author}",
                message.author.id,
                message.content.replace("\n", "\\n")
            ])
    if PURGE_WEBHOOK_URL:
        try:
            async with aiohttp.ClientSession() as session:
                with open(log_filename, "rb") as log_file:
                    data = aiohttp.FormData()
                    data.add_field("content", f"Purged {len(deleted_messages)} messages from {channel.mention}. Log file attached:")
                    data.add_field("file", log_file, filename=log_filename, content_type="text/csv")
                    async with session.post(PURGE_WEBHOOK_URL, data=data) as response:
                        if response.status not in [200, 204]:
                            response_text = await response.text()
                            print(f"Failed to send log file to the purge webhook: {response.status} {response_text}")
        except Exception as e:
            print(f"Error sending log file to the purge webhook: {e}")
    else:
        print("Purge webhook URL not set. Log file was not sent.")
    os.remove(log_filename)

# Slash Command: Avatar Update (Optional)
@bot.event
async def on_user_update(before: discord.User, after: discord.User):
    if before.avatar != after.avatar:
        new_avatar_url = after.avatar.url if after.avatar else None
        message = f"<@{after.id}> changed their profile picture."
        embed = discord.Embed(description=message)
        if new_avatar_url:
            embed.set_image(url=new_avatar_url)
        async with aiohttp.ClientSession() as session:
            await session.post(AVATAR_WEBHOOK_URL, json={"content": message, "embeds": [embed.to_dict()]})

# On Ready
@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    try:
        await bot.tree.sync()
        print("Slash commands synced.")
    except Exception as e:
        print("Error syncing slash commands:", e)
    for guild in bot.guilds:
        print(f"Checking members in guild: {guild.name}")
        try:
            await register_server(guild)
        except Exception as e:
            print("Error auto-registering server:", e)
        try:
            connection = db_connection()
            cursor = connection.cursor()
            query = "SELECT setup FROM servers WHERE Guild_ID = %s"
            cursor.execute(query, (guild.id,))
            result = cursor.fetchone()
            cursor.close()
            connection.close()
            if result and _is_truthy(result[0]):
                for member in guild.members:
                    await add_member_to_users(member)
            else:
                print(f"Server {guild.name} is not set up; not adding members to Users table.")
        except Exception as e:
            print(f"Error checking setup for guild {guild.name}:", e)

bot.run(BOT_TOKEN)