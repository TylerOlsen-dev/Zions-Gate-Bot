import discord
from discord.ext import commands
import aiohttp
import asyncio
import csv
import os
from datetime import datetime
from typing import Optional
from db_connection import db_connection
from dotenv import load_dotenv

load_dotenv()

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
        if result and (result[0] == 1 or result[0] is True or result[0] == "True"):
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
    allowed_roles = []
    try:
        connection = db_connection()
        cursor = connection.cursor()
        if command_name in ("globalban", "globalunban"):
            cursor.execute("SELECT Global_1, Global_2, Global_3 FROM servers WHERE Guild_ID = %s", (guild.id,))
            result = cursor.fetchone()
            allowed_roles = [role for role in result if role is not None] if result else []
        elif command_name in ("localkick", "localban"):
            cursor.execute("SELECT Local_1, Local_2, Local_3 FROM servers WHERE Guild_ID = %s", (guild.id,))
            local_result = cursor.fetchone()
            local_roles = [role for role in local_result if role is not None] if local_result else []
            cursor.execute("SELECT Global_1, Global_2, Global_3 FROM servers WHERE Guild_ID = %s", (guild.id,))
            global_result = cursor.fetchone()
            global_roles = [role for role in global_result if role is not None] if global_result else []
            allowed_roles = local_roles + global_roles
        cursor.close()
        connection.close()
    except Exception as e:
        print("Error retrieving command roles:", e)
        raise discord.app_commands.CheckFailure("Access Denied: Could not verify your permissions.")
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
        return result and result[0] == "True"
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
        if result and (result[0] == 1 or result[0] is True or result[0] == "True"):
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
            if result and (result[0] == 1 or result[0] is True or result[0] == "True"):
                for member in guild.members:
                    await add_member_to_users(member)
            else:
                print(f"Server {guild.name} is not set up; not adding members to Users table.")
        except Exception as e:
            print(f"Error checking setup for guild {guild.name}:", e)

bot.run(BOT_TOKEN)