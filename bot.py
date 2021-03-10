import ast
import asyncio
import random
import sys
import traceback
import discord
from discord.ext import commands
from datetime import datetime
from os import listdir, makedirs, remove, rename
from os.path import isfile, join, exists
import json
import aiohttp

bot_token = "REMPLACER PAR LE TOKEN DE VOTRE BOT"

bot = commands.AutoShardedBot(command_prefix=commands.when_mentioned_or('>'), intents=discord.Intents.all())
bot.remove_command('help')
last_ping = None


def format_datetime(date: datetime):
    week = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]
    day = week[int(date.strftime("%w"))]
    return date.strftime(f"Le %d/%m/%Y ({day}) à %Hh%M")


def get_filename(guild_id: int):
    return datetime.now().strftime(f"{str(guild_id)}-%d-%m-%Y-%H-%M")


def embed_error(error: str, warn: bool = False):
    return discord.Embed(title=f":x: **{error}**", color=0xff0000) if not warn else discord.Embed(
        title=f":warning: **{error}**", color=0xffff00)


def format_name(input_name: str):
    e_chars = "éèêë"
    for e in e_chars:
        input_name = input_name.replace(e, "e")

    a_chars = "àâãä"
    for a in a_chars:
        input_name = input_name.replace(a, "a")

    i_chars = "îìï"
    for i in i_chars:
        input_name = input_name.replace(i, "i")

    u_chars = "ùûü"
    for u in u_chars:
        input_name = input_name.replace(u, "u")

    input_name = input_name.replace(" ", "-")
    input_name = input_name.replace("ç", "c")

    char_list = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-0123456789"
    output_name = ""
    for char in input_name:
        if char in char_list:
            output_name += char

    return output_name if len(output_name) > 0 else "nom-incorrect"


def get_backup_dict(path: str):
    g = None
    try:
        with open(path, "r", encoding='utf8') as f:
            g = json.load(f)
    except Exception:
        pass
    return g


def get_backup_name(path: str):
    g = get_backup_dict(path)
    return g if g is None else g["name"]


def set_roles_position(roles: list):
    new_list = []
    positions = [x["position"] for x in roles]
    while len(positions) > 0:
        new_list.append([x for x in roles if x["position"] == max(positions)][0])
        positions.remove(max(positions))
    return new_list


def prepare_eval(data: str):
    data = data.replace("```py", "```")

    return data


def insert_returns(body):
    # insert return stmt if the last expression is a expression statement
    if isinstance(body[-1], ast.Expr):
        body[-1] = ast.Return(body[-1].value)
        ast.fix_missing_locations(body[-1])

    # for if statements, we insert returns into the body and the orelse
    if isinstance(body[-1], ast.If):
        insert_returns(body[-1].body)
        insert_returns(body[-1].orelse)

    # for with blocks, again we insert returns into the body
    if isinstance(body[-1], ast.With):
        insert_returns(body[-1].body)


def format_code(code: str):
    lines = code.split("\n")
    new_code = "```"

    for i in range(len(lines)):
        new_code += "{}  {} \n".format(str(i + 1), lines[i])

    return new_code + "```"


def hide_sensitive_content(text: str):
    global bot_token

    sensitive_data = [bot_token]
    for data in sensitive_data:
        random_int = random.randint(1, 10)
        text = text.replace(data, "█" * (len(data) + random_int))
    return text


def missing_perms_list(missing_perms: list):
    translate_dict = {
        "create_instant_invite": "Créer une invitation",
        "kick_members": "Expulser des membres",
        "ban_members": "Bannir des membres",
        "administrator": "Administrateur",
        "manage_channels": "Gérer les salons",
        "manage_guild": "Gérer le serveur",
        "add_reactions": "Ajouter des réactions",
        "view_audit_log": "Voir les logs du serveur",
        "priority_speaker": "Priority Speaker",
        "read_messages": "Lire les salons textuels",
        "send_messages": "Envoyer des messages",
        "send_tts_messages": "Envoyer des messages TTS",
        "manage_messages": "Gérer les messages",
        "embed_links": "Intégrer des liens",
        "attach_files": "Attacher des fichiers",
        "read_message_history": "Voir les anciens messages",
        "mention_everyone": "Mentionner @everyone",
        "external_emojis": "Utiliser des émojis externes",
        "connect": "Se connecter",
        "speak": "Parler",
        "mute_members": "Rendre des membres muets",
        "deafen_members": "Rendre des membres sourds",
        "move_members": "Déplacer les membres",
        "use_voice_activation": "Utiliser la détection de voix",
        "change_nickname": "Changer de pseudo",
        "manage_nicknames": "Gérer les pseudos",
        "manage_roles": "Gérer les rôles",
        "manage_webhooks": "Gérer les webhooks",
        "manage_emojis": "Gérer les emojis"
    }

    strmissing = ""
    for p in missing_perms:
        strmissing += translate_dict[p] + ", "
    return strmissing[:-2]


async def clean_guild(guild: discord.guild):
    for channel in guild.channels:
        await channel.delete()

    for i in range(round(len(guild.roles) / 2)):
        for role in guild.roles:
            try:
                await role.delete()
            except Exception:
                pass


async def load_backup(file_path: str, guild: discord.guild, action_reason: str = None):
    with open(file_path, "r", encoding='utf8') as f:
        g = json.load(f)

        backup_roles = []
        if g["backup_date"].startswith("Le"):
            backup_roles = g["roles"][::-1]
        else:
            backup_roles = set_roles_position(g["roles"])

        for role in backup_roles:
            permissions = discord.Permissions()
            if type(role["permissions"]) == list:
                permissions.update(**dict(role["permissions"]))
            else:
                permissions = discord.Permissions(permissions=role["permissions"])

            if role["name"] != "@everyone":
                await guild.create_role(name=role["name"], colour=discord.Colour.from_rgb(*role["colour"]) if type(
                    role["colour"]) == list else discord.Colour(role["colour"]), hoist=role["hoist"],
                                        mentionable=role["mentionable"], permissions=permissions,
                                        reason=action_reason)
            else:
                await guild.default_role.edit(permissions=permissions, reason=action_reason)

        for category in g["categories"]:
            overwrites = []
            for overwrite in category["overwrites"]:
                if overwrite["type"] == "role":
                    if overwrite["name"] not in [x.name for x in guild.roles]:
                        pass
                    else:
                        role = [x for x in guild.roles if x.name == overwrite["name"]][0]
                        permissions = discord.PermissionOverwrite()
                        if type(overwrite["permissions"]) == list:
                            permissions.update(**dict(overwrite["permissions"]))
                        else:
                            permissions.update(**dict(discord.Permissions(permissions=overwrite["permissions"])))
                        overwrites.append((role, permissions))
                else:
                    if "name" in overwrite:
                        if overwrite["name"] not in [x.name for x in guild.members]:
                            pass
                        else:
                            member = [x for x in guild.members if x.name == overwrite["name"]][0]
                            permissions = discord.PermissionOverwrite()
                            if type(overwrite["permissions"]) == list:
                                permissions.update(**dict(overwrite["permissions"]))
                            else:
                                permissions.update(
                                    **dict(discord.Permissions(permissions=overwrite["permissions"])))
                            overwrites.append((member, permissions))
                    else:
                        if overwrite["id"] not in [str(x.id) for x in guild.members]:
                            pass
                        else:
                            member = [x for x in guild.members if str(x.id) == overwrite["id"]][0]
                            permissions = discord.PermissionOverwrite()
                            if type(overwrite["permissions"]) == list:
                                permissions.update(**dict(overwrite["permissions"]))
                            else:
                                permissions.update(
                                    **dict(discord.Permissions(permissions=overwrite["permissions"])))
                            overwrites.append((member, permissions))

            await guild.create_category(category["name"], overwrites=dict(overwrites), reason=action_reason)

        for channel in g["text_channels"]:
            category = None
            try:
                category = [x for x in guild.categories if x.name == channel["category"]][0]
            except:
                pass
            overwrites = []
            for overwrite in channel["overwrites"]:
                if overwrite["type"] == "role":
                    if overwrite["name"] not in [x.name for x in guild.roles]:
                        pass
                    else:
                        role = [x for x in guild.roles if x.name == overwrite["name"]][0]
                        permissions = discord.PermissionOverwrite()
                        if type(overwrite["permissions"]) == list:
                            permissions.update(**dict(overwrite["permissions"]))
                        else:
                            permissions.update(**dict(discord.Permissions(permissions=overwrite["permissions"])))
                        overwrites.append((role, permissions))
                else:
                    if "name" in overwrite:
                        if overwrite["name"] not in [x.name for x in guild.members]:
                            pass
                        else:
                            member = [x for x in guild.members if x.name == overwrite["name"]][0]
                            permissions = discord.PermissionOverwrite()
                            if type(overwrite["permissions"]) == list:
                                permissions.update(**dict(overwrite["permissions"]))
                            else:
                                permissions.update(
                                    **dict(discord.Permissions(permissions=overwrite["permissions"])))
                            overwrites.append((member, permissions))
                    else:
                        if overwrite["id"] not in [str(x.id) for x in guild.members]:
                            pass
                        else:
                            member = [x for x in guild.members if str(x.id) == overwrite["id"]][0]
                            permissions = discord.PermissionOverwrite()
                            if type(overwrite["permissions"]) == list:
                                permissions.update(**dict(overwrite["permissions"]))
                            else:
                                permissions.update(
                                    **dict(discord.Permissions(permissions=overwrite["permissions"])))
                            overwrites.append((member, permissions))

            new_chan = await guild.create_text_channel(channel["name"], overwrites=dict(overwrites),
                                                       reason=action_reason)
            await new_chan.edit(topic=channel["topic"], nsfw=channel["nsfw"], category=category,
                                slowmode_delay=channel["slowmode_delay"], reason=action_reason)

        for channel in g["voice_channels"]:
            overwrites = []
            category = None
            try:
                category = [x for x in guild.categories if x.name == channel["category"]][0]
            except:
                pass
            for overwrite in channel["overwrites"]:
                if overwrite["type"] == "role":
                    if overwrite["name"] not in [x.name for x in guild.roles]:
                        pass
                    else:
                        role = [x for x in guild.roles if x.name == overwrite["name"]][0]
                        permissions = discord.PermissionOverwrite()
                        if type(overwrite["permissions"]) == list:
                            permissions.update(**dict(overwrite["permissions"]))
                        else:
                            permissions.update(**dict(discord.Permissions(permissions=overwrite["permissions"])))
                        overwrites.append((role, permissions))
                else:
                    if "name" in overwrite:
                        if overwrite["name"] not in [x.name for x in guild.members]:
                            pass
                        else:
                            member = [x for x in guild.members if x.name == overwrite["name"]][0]
                            permissions = discord.PermissionOverwrite()
                            if type(overwrite["permissions"]) == list:
                                permissions.update(**dict(overwrite["permissions"]))
                            else:
                                permissions.update(
                                    **dict(discord.Permissions(permissions=overwrite["permissions"])))
                            overwrites.append((member, permissions))
                    else:
                        if overwrite["id"] not in [str(x.id) for x in guild.members]:
                            pass
                        else:
                            member = [x for x in guild.members if str(x.id) == overwrite["id"]][0]
                            permissions = discord.PermissionOverwrite()
                            if type(overwrite["permissions"]) == list:
                                permissions.update(**dict(overwrite["permissions"]))
                            else:
                                permissions.update(
                                    **dict(discord.Permissions(permissions=overwrite["permissions"])))
                            overwrites.append((member, permissions))

            new_chan = await guild.create_voice_channel(channel["name"], overwrites=dict(overwrites),
                                                        reason=action_reason)
            await new_chan.edit(
                bitrate=channel["bitrate"] if channel["bitrate"] <= 96000 and channel["bitrate"] >= 8000 else 64000,
                user_limit=channel["user_limit"], category=category, reason=action_reason)

        for channel in g["text_channels"]:
            await [x for x in guild.text_channels if x.name == channel["name"]][0].edit(
                position=channel["position"] if channel["position"] < len(guild.text_channels) else len(
                    guild.text_channels) - 1, reason=action_reason)

        for channel in g["voice_channels"]:
            await [x for x in guild.voice_channels if x.name == channel["name"]][0].edit(
                position=channel["position"] if channel["position"] < len(guild.voice_channels) else len(
                    guild.voice_channels) - 1, reason=action_reason)

        for category in g["categories"]:
            await [x for x in guild.categories if x.name == category["name"]][0].edit(
                position=category["position"] if category["position"] < len(guild.categories) else len(
                    guild.categories) - 1, reason=action_reason)

        guild_bans = [ban_entry[1] for ban_entry in await guild.bans()]
        backup_bans = []
        backup_reasons = []
        for ban_entry in g["bans"]:
            try:
                user = await bot.fetch_user(ban_entry["id"])
                backup_bans.append(user)
                backup_reasons.append(ban_entry["reason"])
            except Exception:
                pass

        for user in guild_bans:
            if not user in backup_bans:
                try:
                    await guild.unban(user, reason=action_reason)
                except Exception:
                    pass

        for user in backup_bans:
            if not user in guild_bans:
                try:
                    await guild.ban(user=user, reason=backup_reasons[backup_bans.index(user)])
                except Exception:
                    pass

        for member in g["members"]:
            guild_member = guild.get_member(int(member["id"]))
            if guild_member is not None and guild_member != guild.me:
                if "nick" in member and guild_member != guild.owner and guild_member.nick != member["nick"]:
                    try:
                        await guild_member.edit(nick=member["nick"], reason=action_reason)
                    except Exception:
                        pass

                if len(guild_member.roles) != 1:
                    continue

                member_roles = [discord.utils.get(guild.roles, name=role_name) for role_name in member["roles"]]
                member_roles = [m_r for m_r in member_roles if m_r is not None and not m_r.managed]
                for role in member_roles:
                    try:
                        await guild_member.add_roles(role, reason=action_reason)
                    except Exception:
                        pass

        guild_icon = None
        try:
            async with aiohttp.ClientSession() as ses:
                async with ses.get(g["icon"]) as r:
                    guild_icon = await r.read()
        except Exception:
            pass

        await guild.edit(name=g["name"], region=discord.VoiceRegion(g["region"]),
                         afk_channel=[x for x in guild.voice_channels if x.name == g["afk_channel"]][0] if g[
                             "afk_channel"] else None, afk_timeout=g["afk_timeout"],
                         verification_level=discord.VerificationLevel(g["verification_level"]),
                         default_notifications=discord.NotificationLevel.only_mentions if g[
                                                                                              "default_notifications"] == "only_mentions" else discord.NotificationLevel.all_messages,
                         explicit_content_filter=discord.ContentFilter(g["explicit_content_filter"]),
                         system_channel=[x for x in guild.text_channels if x.name == g["system_channel"]][0] if g[
                             "system_channel"] else None, reason=action_reason)

        try:
            await guild.edit(icon=guild_icon, reason=action_reason)
        except Exception:
            pass

        embed = discord.Embed(title="✅ Voilà !",
                              description="Votre sauvegarde a été chargée, à l'exception des emojis qui vont être prochainement importés.\nCette opération peut être longue et incomplète.\nDésolé si cela est le cas.",
                              color=0x008040)
        await guild.text_channels[0].send(content="@here", embed=embed)

        backup_emojis = [emoji["name"] for emoji in g["emojis"]]
        for emoji in guild.emojis:
            if not emoji.name in backup_emojis:
                await emoji.delete(reason=action_reason)

        guild_emojis = [emoji.name for emoji in guild.emojis]
        for emoji in g["emojis"]:
            if emoji["name"] in guild_emojis:
                continue

            try:
                img = None
                async with aiohttp.ClientSession() as ses:
                    async with ses.get(emoji["url"]) as r:
                        img = await r.read()
                await guild.create_custom_emoji(name=emoji["name"], image=img, reason=action_reason)
            except Exception:
                pass


async def create_backup(file_path: str, guild: discord.Guild):
    saved_guild = {
        "name": guild.name,
        "region": str(guild.region),
        "afk_timeout": guild.afk_timeout,
        "afk_channel": guild.afk_channel.name if guild.afk_channel else None,
        "system_channel": guild.system_channel.name if guild.system_channel else None,
        "icon": str(guild.icon_url_as(static_format='jpg', format='jpg', size=4096)),
        "verification_level": ["none", "low", "medium", "high", "extreme"].index(
            str(guild.verification_level)),
        "default_notifications": "only_mentions" if guild.default_notifications == discord.NotificationLevel.only_mentions else "all_messages",
        "explicit_content_filter": ["disabled", "no_role", "all_members"].index(str(guild.explicit_content_filter)),
        "roles": [],
        "categories": [],
        "text_channels": [],
        "voice_channels": [],
        "emojis": [],
        "bans": [],
        "members": [],
        "backup_date": format_datetime(datetime.now())
    }

    for role in guild.roles:
        if role.managed:
            continue

        role_dict = {
            "name": role.name,
            "permissions": list(role.permissions),
            "colour": role.colour.to_rgb(),
            "hoist": role.hoist,
            "position": role.position,
            "mentionable": role.mentionable
        }

        saved_guild["roles"].append(role_dict)

    for category in guild.categories:
        category_dict = {
            "name": category.name,
            "position": category.position,
            "channels": [],
            "overwrites": []
        }

        for channel in category.channels:
            category_dict["channels"].append(channel.name)

        for overwrite in category.overwrites:
            overwrite_dict = {
                "name": overwrite.name,
                "permissions": list(category.overwrites_for(overwrite)),
                "type": "member" if type(overwrite) == discord.Member else "role"
            }

            category_dict["overwrites"].append(overwrite_dict)

        saved_guild["categories"].append(category_dict)

    for channel in guild.text_channels:
        channel_dict = {
            "name": channel.name,
            "topic": channel.topic,
            "position": channel.position,
            "sync_permissions": channel.permissions_synced,
            "slowmode_delay": channel.slowmode_delay,
            "nsfw": channel.is_nsfw(),
            "overwrites": [],
            "category": channel.category.name if channel.category else None
        }

        for overwrite in channel.overwrites:
            overwrite_dict = {
                "name": overwrite.name,
                "permissions": list(channel.overwrites_for(overwrite)),
                "type": "member" if type(overwrite) == discord.Member else "role"
            }

            channel_dict["overwrites"].append(overwrite_dict)

        saved_guild["text_channels"].append(channel_dict)

    for channel in guild.voice_channels:
        channel_dict = {
            "name": channel.name,
            "position": channel.position,
            "sync_permissions": channel.permissions_synced,
            "user_limit": channel.user_limit,
            "bitrate": channel.bitrate,
            "overwrites": [],
            "category": channel.category.name if channel.category else None
        }

        for overwrite in channel.overwrites:
            overwrite_dict = {
                "name": overwrite.name,
                "permissions": list(channel.overwrites_for(overwrite)),
                "type": "member" if type(overwrite) == discord.Member else "role"
            }

            channel_dict["overwrites"].append(overwrite_dict)

        saved_guild["voice_channels"].append(channel_dict)

    for emoji in guild.emojis:
        emoji_dict = {
            "name": emoji.name,
            "url": str(emoji.url)
        }

        saved_guild["emojis"].append(emoji_dict)

    for ban in await guild.bans():
        ban_dict = {
            "id": ban[1].id,
            "reason": ban[0]
        }

        saved_guild["bans"].append(ban_dict)

    for member in guild.members:
        if member == guild.me:
            continue

        if len(member.roles) == 1 and member.nick is None:
            continue

        member_dict = {
            "id": member.id,
            "nick": member.nick,
            "roles": [role.name for role in member.roles if role != guild.default_role]
        }

        saved_guild["members"].append(member_dict)

    with open(file_path, "w+") as f:
        json.dump(saved_guild, f)


async def update_status():
    await bot.change_presence(
        activity=discord.Streaming(name=f">help | Backup bot by Lcram33 | Sur {str(len(bot.guilds))} serveurs",
                                   url="https://www.twitch.tv/lcram33"), status=discord.Status.online)


@bot.event
async def on_command_error(ctx, error):
    appinfo = await bot.application_info()

    if isinstance(error, (commands.CommandNotFound, commands.DisabledCommand, commands.NotOwner)):
        return
    elif isinstance(error, commands.NoPrivateMessage):
        embed = discord.Embed(title=":warning: **Cette commande ne peut pas être effectuée en mp.**",
                              color=0xfac801)
        return await ctx.send(embed=embed)
    elif isinstance(error, commands.CommandOnCooldown):
        if ctx.author == appinfo.owner:
            ctx.command.reset_cooldown(ctx)
            await bot.process_commands(ctx.message)
        else:
            await ctx.message.add_reaction("⏰")
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(title=":x: **Il manque le paramètre `{}`.**".format(error.param.name), color=0xff0000)
        return await ctx.send(embed=embed)
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(title=":x: **Les paramètres n'ont pas été entrés correctement.**", color=0xff0000)
        return await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingPermissions):
        if ctx.author == appinfo.owner:
            await ctx.reinvoke()
            return

        embed = discord.Embed(
            title=":x: **Vous devez avoir les permissions suivantes pour effectuer cette commande : `{}`.**".format(
                missing_perms_list(error.missing_perms)), color=0xff0000)
        return await ctx.send(embed=embed)
    elif isinstance(error, commands.BotMissingPermissions):
        embed = discord.Embed(title=":x: **Le bot a besoin des permissions suivantes : `{}`.**".format(
            missing_perms_list(error.missing_perms)), color=0xff0000)
        return await ctx.send(embed=embed)
    else:
        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
        embed = discord.Embed(title=":x: Une erreur inconnue s'est produite.", color=0xff0000)
        return await ctx.send(embed=embed)


@bot.event
async def on_guild_remove(guild):
    await update_status()


@bot.event
async def on_ready():
    print(
        f"Démarré en tant que {bot.user.name}#{str(bot.user.discriminator)}, {str(bot.user.id)} ({str(len(bot.guilds))} serveurs)")
    await update_status()


@bot.event
async def on_guild_join(guild):
    await update_status()


@bot.command()
@commands.is_owner()
async def boteval(ctx):
    """Evaluates input.
    Input is interpreted as newline seperated statements.
    If the last statement is an expression, that is the return value.
    Usable globals:
      - `bot`: the bot instance
      - `discord`: the discord module
      - `commands`: the discord.ext.commands module
      - `ctx`: the invokation context
      - `__import__`: the builtin `__import__` function
    Such that `>eval 1 + 1` gives `2` as the result.
    The following invokation will cause the bot to send the text '9'
    to the channel of invokation and return '3' as the result of evaluating
    >eval ```
    a = 1 + 2
    b = a * 2
    await ctx.send(a + b)
    a
    ```
    """

    global old_body
    result = ""
    try:
        fn_name = "_eval_expr"
        cmd = prepare_eval(ctx.message.content.replace(">boteval ", ""))
        cmd = cmd.strip("` ")

        # add a layer of indentation
        cmd = "\n".join("    {}".format(i) for i in cmd.splitlines())

        # wrap in async def body
        body = "async def {}():\n{}".format(fn_name, cmd)
        old_body = body

        parsed = ast.parse(body)
        body = parsed.body[0].body

        insert_returns(body)

        env = {
            'bot': ctx.bot,
            'discord': discord,
            'commands': commands,
            'ctx': ctx,
            '__import__': __import__
        }

        exec(compile(parsed, filename="<ast>", mode="exec"), env)
        result = (await eval("{}()".format(fn_name), env))
        result = ":white_check_mark: Résultat :\n```" + str(result) + "```"
    except Exception as e:
        result = ":warning: L'erreur suivante s'est produite :\n```" + str(e) + "``` \n :arrow_right: Code : {}".format(
            format_code(old_body))

    await ctx.send(hide_sensitive_content(result))


@bot.command()
@commands.cooldown(3, 10 * 60, type=commands.BucketType.guild)
@commands.guild_only()
async def health(ctx):
    bot_info = ""

    b_role = discord.utils.get(ctx.message.guild.roles, name=bot.user.name)
    if b_role is None:
        bot_info += "❌ Le rôle du bot n'a pas été trouvé, veuillez le renommer en `{}`.\n".format(
            bot.user.name)
    else:
        bot_info += "✅ Le rôle du bot a bien été trouvé\n"

    if not ctx.message.guild.me.guild_permissions.administrator:
        bot_info += "❌ Le bot ne possède pas la permission administrateur. Veuillez lui accorder, ou toutes les permissions.\n"
    else:
        bot_info += "✅ Permission `Administrateur` accordée au bot\n"

    pob = "unknown"
    if b_role is not None:
        pob = "✅ Le rôle du bot est le plus haut"
        if b_role.position != len(ctx.message.guild.roles) - 1:
            pob = ":negative_squared_cross_mark: Le rôle du bot n'est pas le plus haut"
        for r in ctx.message.guild.roles:
            if r.position > b_role.position and r.managed:
                pob = "⚠️ Le rôle du bot est en-dessous du rôle d'un autre bot, si un bot malveillant à un rôle au dessus de GuildEdit ce dernier ne pourra rien faire..."
                break
    bot_info += pob + "\n"

    guild_info = ""

    roles_m = ""
    for r in ctx.guild.roles:
        if r.mentionable:
            roles_m += r.mention + " "
    if len(roles_m) == 0:
        guild_info = "✅ Aucun rôle mentionnable\n"
    else:
        guild_info = "⚠️ Rôles mentionnables : {}\n".format(roles_m)

    roles_a = ""
    for r in ctx.guild.roles:
        if r.permissions.administrator and r.name != bot.user.name:
            roles_a += r.mention + " "
    if len(roles_a) == 0:
        guild_info += "✅ Aucun rôle ne possédant la permission administrateur\n"
    else:
        guild_info += "❓ Rôles possédant la permission administrateur : {}\n".format(roles_a)

    roles_me = ""
    for r in ctx.guild.roles:
        if r.permissions.mention_everyone:
            roles_me += r.mention + " "
    if len(roles_me) == 0:
        guild_info += "✅ Aucun rôle ne possédant la permission de mentionner everyone\n"
    else:
        guild_info += "❓ Rôles possédant la permission de mentionner everyone : {}\n".format(roles_me)

    roles_stm = ""
    for r in ctx.guild.roles:
        if r.permissions.send_tts_messages:
            roles_stm += r.mention + " "
    if len(roles_stm) == 0:
        guild_info += "✅ Aucun rôle ne possédant la permission d'envoyer des messages tts\n"
    else:
        guild_info += "❓ Rôles possédant la permission d'envoyer des messages tts : {}\n".format(roles_stm)

    if str(ctx.guild.verification_level) in ["medium", "high", "extreme"]:
        guild_info += "✅ Niveau de vérification du serveur correct"
    elif str(ctx.guild.verification_level) == "low":
        guild_info += ":negative_squared_cross_mark: Niveau de vérification du serveur légèrement faible, il est conseillé de l'augmenter d'un niveau"
    else:
        guild_info += "⚠️ Niveau de vérification du serveur trop faible."

    embed = discord.Embed(title="💊 Diagnostic", description="Informations quant aux problèmes éventuels.",
                          color=0x36393f)
    embed.add_field(name="Problèmes liés au bot", value=bot_info, inline=False)
    embed.add_field(name="Problèmes de sécurité du serveur", value=guild_info, inline=False)
    embed.set_footer(
        text="✅ : Aucun problème détecté\n⚠️ Avertissement\n❎ Problème mineur (ne gêne pas une utilisation normale du bot)\n❌ Erreur critique")
    await ctx.send(embed=embed)


@bot.command()
@commands.cooldown(1, 5 * 60, type=commands.BucketType.user)
async def help(ctx):
    embed = discord.Embed(title="Commandes", description="""
__Catégorie : Backup__

**>health**, cooldown : 3 en 10min/serveur.
**>createbackup**, permissions : Administrateur, cooldown : 3min/serveur.
**>updatebackup (nom)**, permissions : Administrateur, cooldown : 3min/serveur.
**>backuplist**, cooldown : 2min/user.
**>backupinfos (nom)**, cooldown : 2min/user.
**>renamebackup (nom) "(nouveau nom)"**, cooldown : 2 en 3min/user.
**>deletebackup (nom)**, cooldown : 2 en 3min/user.
**>roleslist (nom)**, cooldown : 2min/user.
**>channelslist (nom)**, cooldown : 2min/user.
**>emoteslist (nom)**, cooldown : 2min/user.
**>emoteinfo (nom)**, cooldown : 10 en 5min/user.
**>roleinfo (nom) (nom rôle)**, cooldown : 10 en 5min/user.
**>textinfo & >vocinfo (nom) (nom salon)**, cooldown : 10 en 5min/user.
**>loadbackup (nom)** **Attention, cela écrase le serveur.** Permissions : Administrateur. Cooldown : 5min/serveur.
**>loadroles (nom)** : Charge les rôles de la sauvegarde indiquée. Permissions : Administrateur. Cooldown : 5min/serveur.
**>loadchannels (nom)** : Charge les salons de la sauvegarde indiquée. Permissions : Administrateur. Cooldown : 5min/serveur.
**>loadbans (nom)** : Charge les bannissemnts de la sauvegarde indiquée. Permissions : Administrateur. Cooldown : 5min/serveur.
**>loademojis (nom)** : Charge les emojis de la sauvegarde indiquée. Permissions : Administrateur. Cooldown : 5min/serveur.
**>loadsettings (nom)** : Charge les paramètres de la sauvegarde indiquée. Permissions : Administrateur. Cooldown : 5min/serveur.
**>loadmembers (nom)** : Charge les pseudos et rôles des membres de la sauvegarde indiquée. Permissions : Administrateur. Cooldown : 5min/serveur.
        """, color=0x36393f)
    embed.set_footer(text="Remarque : si une commande est en cooldown, le bot réagira à votre message avec ⏰")

    try:
        await ctx.author.send(embed=embed)
        await ctx.message.add_reaction(emoji="📩")
    except Exception as e:
        await ctx.send(
            ":x: **Impossible de vous envoyer un mp. Les avez-vous activés ?**\n{}".format(ctx.author.mention))


@bot.command()
@commands.cooldown(3, 10 * 60, type=commands.BucketType.user)
async def ping(ctx):
    global last_ping

    new_ping = round(bot.latency * 1000) + 1
    old_ping = last_ping
    last_ping = new_ping

    embed = discord.Embed(title=":ping_pong: **Pong ! `{}` ms**".format(str(new_ping)), color=0x36393f)
    if old_ping is not None:
        percent = round(100 - 100 * old_ping / new_ping, 2)
        if percent < 0:
            percent = "↘️" + str(percent) + "%"
        elif percent == 0:
            percent = "🔄" + str(percent) + "%"
        else:
            percent = "🔼+" + str(percent) + "%"
        embed.set_footer(text="Ping précédent : {} ms {}".format(str(old_ping), percent))
    response = await ctx.send(embed=embed)

    try:
        await ctx.message.delete()
    except Exception:
        pass

    await asyncio.sleep(6)
    await response.delete()


@bot.command()
async def updatestatus(ctx):
    await update_status()
    await ctx.message.add_reaction(emoji='✅')


@bot.command()
async def stop(ctx):
    embed_confirmation = discord.Embed(title="🛑 Confirmation de l'arrêt", description="Stopper le bot ?",
                                       color=0xff0000)
    embed_confirmation.add_field(name="Annulation", value="Ne faîtes rien, la commande s'annulera dans 30s.",
                                 inline=False)
    confirm = await ctx.send(embed=embed_confirmation)
    await confirm.add_reaction(emoji='✅')

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) == '✅'

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(":x: Délai d'atente dépassé, veuillez retaper la commande.")
        return

    embed = discord.Embed(title="🌙 Arrêt.")
    await confirm.edit(embed=embed)
    try:
        await confirm.clear_reactions()
    except Exception:
        pass

    await bot.close()
    sys.exit("Bot down par commande.")


@bot.command()
@commands.cooldown(1, 2 * 60, type=commands.BucketType.user)
async def emoteslist(ctx, backup_name):
    path = "./backups/{}/".format(str(ctx.author.id))

    g = get_backup_dict(join(path, backup_name + ".json"))
    if g is None:
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    if len(g["emojis"]) == 0:
        embed = discord.Embed(title=g["name"],
                              description="Fichier : `{}`\nCréation : **{}**".format(backup_name,
                                                                                     g["backup_date"]),
                              color=0x008080)
        embed.set_thumbnail(url=g["icon"])
        embed.add_field(name="Emojis", value="Aucun")
        await ctx.send(embed=embed)
        return

    str_emojis = ""
    page_count = 1
    for emoji in g["emojis"][::-1]:
        if len(str_emojis) + len(emoji["name"] + "\n") >= 1024:
            embed = discord.Embed(title=g["name"],
                                  description="Fichier : `{}`\nCréation : **{}**".format(backup_name,
                                                                                         g["backup_date"]),
                                  color=0x008080)
            embed.set_thumbnail(url=g["icon"])
            embed.add_field(name="Emojis", value=str_emojis)
            embed.set_footer(text="Page " + str(page_count))
            await ctx.send(embed=embed)

            page_count += 1
            str_emojis = ""

        str_emojis += emoji["name"] + "\n"

    if len(str_emojis) > 0:
        embed = discord.Embed(title=g["name"],
                              description="Fichier : `{}`\nCréation : **{}**".format(backup_name,
                                                                                     g["backup_date"]),
                              color=0x008080)
        embed.set_thumbnail(url=g["icon"])
        embed.add_field(name="Emojis", value=str_emojis)
        embed.set_footer(text="Page " + str(str_emojis))
        await ctx.send(embed=embed)


@bot.command()
@commands.cooldown(1, 2 * 60, type=commands.BucketType.user)
async def roleslist(ctx, backup_name):
    path = "./backups/{}/".format(str(ctx.author.id))

    g = get_backup_dict(join(path, backup_name + ".json"))
    if g is None:
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    if len(g["roles"]) == 0:
        embed = discord.Embed(title=g["name"],
                              description="Fichier : `{}`\nCréation : **{}**".format(backup_name,
                                                                                     g["backup_date"]),
                              color=0x008080)
        embed.set_thumbnail(url=g["icon"])
        embed.add_field(name="Rôles", value="Aucun")
        await ctx.send(embed=embed)
        return

    str_roles = ""
    page_count = 1
    for role in g["roles"][::-1]:
        if role["name"] != "@everyone":
            if len(str_roles) + len(role["name"] + "\n") >= 1024:
                embed = discord.Embed(title=g["name"],
                                      description="Fichier : `{}`\nCréation : **{}**".format(backup_name,
                                                                                             g["backup_date"]),
                                      color=0x008080)
                embed.set_thumbnail(url=g["icon"])
                embed.add_field(name="Rôles", value=str_roles)
                embed.set_footer(text="Page " + str(page_count))
                await ctx.send(embed=embed)

                page_count += 1
                str_roles = ""

            str_roles += role["name"] + "\n"

    if len(str_roles) > 0:
        embed = discord.Embed(title=g["name"],
                              description="Fichier : `{}`\nCréation : **{}**".format(backup_name,
                                                                                     g["backup_date"]),
                              color=0x008080)
        embed.set_thumbnail(url=g["icon"])
        embed.add_field(name="Rôles", value=str_roles)
        embed.set_footer(text="Page " + str(page_count))
        await ctx.send(embed=embed)


@bot.command()
@commands.cooldown(10, 5 * 60, type=commands.BucketType.user)
async def roleinfo(ctx, backup_name, role_name):
    path = "./backups/{}/".format(str(ctx.author.id))

    g = get_backup_dict(join(path, backup_name + ".json"))
    if g is None:
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    role = [role for role in g["roles"] if role["name"].find(role_name) > -1]
    if len(role) == 0:
        await ctx.send(embed=embed_error("Rôle introuvable.", True))
        return

    role = role[0]
    translate_dict = {
        "create_instant_invite": "Créer une invitation",
        "kick_members": "Expulser des membres",
        "ban_members": "Bannir des membres",
        "administrator": "Administrateur",
        "manage_channels": "Gérer les salons",
        "manage_guild": "Gérer le serveur",
        "add_reactions": "Ajouter des réactions",
        "view_audit_log": "Voir les logs du serveur",
        "priority_speaker": "Priority Speaker",
        "read_messages": "Lire les salons textuels",
        "send_messages": "Envoyer des messages",
        "send_tts_messages": "Envoyer des messages TTS",
        "manage_messages": "Gérer les messages",
        "embed_links": "Intégrer des liens",
        "attach_files": "Attacher des fichiers",
        "read_message_history": "Voir les anciens messages",
        "mention_everyone": "Mentionner @everyone",
        "external_emojis": "Utiliser des émojis externes",
        "connect": "Se connecter",
        "speak": "Parler",
        "mute_members": "Rendre des membres muets",
        "deafen_members": "Rendre des membres sourds",
        "move_members": "Déplacer les membres",
        "use_voice_activation": "Utiliser la détection de voix",
        "change_nickname": "Changer de pseudo",
        "manage_nicknames": "Gérer les pseudos",
        "manage_roles": "Gérer les rôles",
        "manage_webhooks": "Gérer les webhooks",
        "manage_emojis": "Gérer les emojis"
    }

    strperms = ""
    role_perms = role["permissions"]
    if type(role["permissions"]) == int:
        role_perms = dict(discord.Permissions(permissions=role["permissions"]))
    for p in role_perms:
        if p[0] in translate_dict and p[1]:
            strperms += translate_dict[p[0]] + "\n"

    role_colour = None
    if type(role["colour"]) == int:
        role_colour = discord.Color(value=role["colour"])
    else:
        role_colour = discord.Color.from_rgb(role["colour"][0], role["colour"][1], role["colour"][2])

    embed = discord.Embed(title=role["name"],
                          description="Fichier : `{}`\nServeur : `{}`\nCréation : **{}**".format(backup_name, g["name"],
                                                                                                 g["backup_date"]),
                          color=role_colour)
    embed.set_thumbnail(url=g["icon"])
    embed.add_field(name="Mentionable", value="Oui" if role["mentionable"] else "Non", inline=True)
    embed.add_field(name="Affiché séparément", value="Oui" if role["hoist"] else "Non", inline=True)
    embed.add_field(name="Permissions", value="Pas de permissions" if len(strperms) == 0 else strperms, inline=False)
    await ctx.send(embed=embed)


@bot.command()
@commands.cooldown(10, 5 * 60, type=commands.BucketType.user)
async def vocinfo(ctx, backup_name, voc_name):
    path = "./backups/{}/".format(str(ctx.author.id))

    g = get_backup_dict(join(path, backup_name + ".json"))
    if g is None:
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    voice_channel = [channel for channel in g["voice_channels"] if channel["name"].find(voc_name) > -1]
    if len(voice_channel) == 0:
        await ctx.send(embed=embed_error("Salon introuvable.", True))
        return

    voice_channel = voice_channel[0]

    str_overwrites = ""
    for overwrite in voice_channel["overwrites"]:
        str_overwrites += overwrite["name"] + '\n'
    if len(str_overwrites) == 0:
        str_overwrites = "Personne"

    embed = discord.Embed(title=voice_channel["name"],
                          description="Fichier : `{}`\nServeur : `{}`\nCréation : **{}**".format(backup_name, g["name"],
                                                                                                 g["backup_date"]),
                          color=0x008080)
    embed.set_thumbnail(url=g["icon"])
    embed.add_field(name="Limite d'utilisateurs", value=':infinity:' if voice_channel["user_limit"] == 0 else str(voice_channel["user_limit"]), inline=False)
    embed.add_field(name="Débit binaire", value=str(voice_channel["bitrate"]//1000) + 'kbps', inline=True)
    embed.add_field(name="Catégorie", value="Aucune" if voice_channel["category"] is None else voice_channel["category"], inline=True)
    embed.add_field(name="Permissions modifiées pour", value="Trop de texte à afficher." if len(str_overwrites) > 500 else str_overwrites, inline=False)
    await ctx.send(embed=embed)


@bot.command()
@commands.cooldown(10, 5 * 60, type=commands.BucketType.user)
async def textinfo(ctx, backup_name, text_name):
    path = "./backups/{}/".format(str(ctx.author.id))

    g = get_backup_dict(join(path, backup_name + ".json"))
    if g is None:
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    text_channel = [channel for channel in g["text_channels"] if channel["name"].find(text_name) > -1]
    if len(text_channel) == 0:
        await ctx.send(embed=embed_error("Salon introuvable.", True))
        return

    text_channel = text_channel[0]

    str_overwrites = ""
    for overwrite in text_channel["overwrites"]:
        str_overwrites += overwrite["name"] + '\n'
    if len(str_overwrites) == 0:
        str_overwrites = "Personne"

    embed = discord.Embed(title=text_channel["name"],
                          description="Fichier : `{}`\nServeur : `{}`\nCréation : **{}**".format(backup_name, g["name"],
                                                                                                 g["backup_date"]),
                          color=0x008080)
    embed.set_thumbnail(url=g["icon"])
    embed.add_field(name="Sujet", value="Aucun" if text_channel["topic"] is None else text_channel["topic"], inline=False)
    embed.add_field(name="Mode lent", value="Non" if text_channel["slowmode_delay"] == 0 else str(text_channel["slowmode_delay"]) + 's', inline=True)
    embed.add_field(name="Catégorie", value="Aucune" if text_channel["category"] is None else text_channel["category"], inline=True)
    embed.add_field(name="NSFW", value="Oui" if text_channel["nsfw"] else "Non", inline=True)
    embed.add_field(name="Permissions modifiées pour", value="Trop de texte à afficher." if len(str_overwrites) > 500 else str_overwrites, inline=False)
    await ctx.send(embed=embed)


@bot.command()
@commands.cooldown(10, 5 * 60, type=commands.BucketType.user)
async def emoteinfo(ctx, backup_name, emoji_name):
    path = "./backups/{}/".format(str(ctx.author.id))

    g = get_backup_dict(join(path, backup_name + ".json"))
    if g is None:
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    emoji = [emoji for emoji in g["emojis"] if emoji["name"].find(emoji_name) > -1]
    if len(emoji) == 0:
        await ctx.send(embed=embed_error("Emoji introuvable.", True))
        return

    emoji = emoji[0]

    embed = discord.Embed(title=emoji["name"],
                          description="Fichier : `{}`\nServeur : `{}`\nCréation : **{}**".format(backup_name, g["name"],
                                                                                                 g["backup_date"]),
                          color=0x008080)
    embed.set_thumbnail(url=emoji["url"])
    await ctx.send(embed=embed)

@bot.command()
@commands.cooldown(1, 2 * 60, type=commands.BucketType.user)
async def channelslist(ctx, backup_name):
    path = "./backups/{}/".format(str(ctx.author.id))

    g = get_backup_dict(join(path, backup_name + ".json"))
    if g is None:
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    if len(g["text_channels"]) == 0:
        embed = discord.Embed(title=g["name"],
                              description="Fichier : `{}`\nCréation : **{}**".format(backup_name, g["backup_date"]),
                              color=0x008080)
        embed.set_thumbnail(url=g["icon"])
        embed.add_field(name="Salons textuels", value="Aucun", inline=False)
        await ctx.send(embed=embed)
    else:
        strtext = ""
        page_count = 1
        for text_channel in g["text_channels"]:
            channel = text_channel["name"]
            if text_channel["category"] is not None:
                channel += " (dans {})".format(text_channel["category"])

            if len(strtext) + len(channel + "\n") >= 1024:
                embed = discord.Embed(title=g["name"],
                                      description="Fichier : `{}`\nCréation : **{}**".format(backup_name,
                                                                                             g["backup_date"]),
                                      color=0x008080)
                embed.set_thumbnail(url=g["icon"])
                embed.add_field(name="Salons textuels", value=strtext, inline=False)
                embed.set_footer(text="Page " + str(page_count))
                await ctx.send(embed=embed)

                strtext = ""
                page_count += 1

            strtext += channel + "\n"

        if len(strtext) > 0:
            embed = discord.Embed(title=g["name"],
                                  description="Fichier : `{}`\nCréation : **{}**".format(backup_name, g["backup_date"]),
                                  color=0x008080)
            embed.set_thumbnail(url=g["icon"])
            embed.add_field(name="Salons textuels", value=strtext, inline=False)
            embed.set_footer(text="Page " + str(page_count))
            await ctx.send(embed=embed)

    if len(g["voice_channels"]) == 0:
        embed = discord.Embed(title=g["name"],
                              description="Fichier : `{}`\nCréation : **{}**".format(backup_name, g["backup_date"]),
                              color=0x008080)
        embed.set_thumbnail(url=g["icon"])
        embed.add_field(name="Salons vocaux", value="Aucun", inline=False)
        await ctx.send(embed=embed)
    else:
        strvoice = ""
        page_count = 1
        for voice_channel in g["voice_channels"]:
            channel = voice_channel["name"]
            if voice_channel["category"] is not None:
                channel += " (dans {})".format(voice_channel["category"])

            if len(strvoice) + len(channel + "\n") >= 1024:
                embed = discord.Embed(title=g["name"],
                                      description="Fichier : `{}`\nCréation : **{}**".format(backup_name,
                                                                                             g["backup_date"]),
                                      color=0x008080)
                embed.set_thumbnail(url=g["icon"])
                embed.add_field(name="Salons vocaux", value=strvoice, inline=False)
                embed.set_footer(text="Page " + str(page_count))
                await ctx.send(embed=embed)

                page_count += 1
                strvoice = ""

            strvoice += channel + "\n"

        if len(strvoice) > 0:
            embed = discord.Embed(title=g["name"],
                                  description="Fichier : `{}`\nCréation : **{}**".format(backup_name, g["backup_date"]),
                                  color=0x008080)
            embed.set_thumbnail(url=g["icon"])
            embed.add_field(name="Salons vocaux", value=strvoice, inline=False)
            embed.set_footer(text="Page " + str(page_count))
            await ctx.send(embed=embed)


@bot.command()
@commands.cooldown(1, 2 * 60, type=commands.BucketType.user)
async def backupinfos(ctx, backup_name):
    path = "./backups/{}/".format(str(ctx.author.id))

    g = get_backup_dict(join(path, backup_name + ".json"))
    if g is None:
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    verification_level = ["Aucun", "Faible", "Moyen", "(╯°□°）╯︵ ┻━┻", "┻━┻ ﾐヽ(ಠ益ಠ)ノ彡┻━┻"]
    explicit_content_filter = ["Aucun", "Sans rôles", "Tous les membres"]

    embed = discord.Embed(title=g["name"],
                          description="Fichier : `{}`\nCréation : **{}**".format(backup_name, g["backup_date"]),
                          color=0x008080)
    embed.set_thumbnail(url=g["icon"])
    embed.add_field(name="Caractéristiques",
                    value="""
💬 Salons textuels : {}
🔊 Salons vocaux : {}
🚩 Rôles : {}
:slight_smile: Emojis : {}
:no_entry: Bannissements : {}
:man: Membres : {}
                    """.format(
                        str(len(g["text_channels"])),
                        str(len(g["voice_channels"])),
                        str(len(g["roles"])),
                        str(len(g["emojis"])),
                        str(len(g["bans"])),
                        str(len(g["members"]))),
                    inline=True)
    embed.add_field(name="Paramètres", value="""
Région : `{}`
AFK : `{} ({})`
System channel : `{}`
Niveau de vérification : `{}`
Notifications : `{}`
Filtre de contenu explicit : `{}`
    """.format(g["region"], g["afk_channel"],
               str(int(g["afk_timeout"] / 60)) + "min" if g["afk_timeout"] != 3600 else "1h", g["system_channel"],
               verification_level[g["verification_level"]],
               "Tous les messages" if g["default_notifications"] == "all_messages" else "@mentions seulement",
               explicit_content_filter[g["explicit_content_filter"]]), inline=True)
    await ctx.send(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 5 * 60, type=commands.BucketType.guild)
@commands.guild_only()
async def loadbackup(ctx, backup_name):
    if not ctx.guild.me.guild_permissions.administrator:
        raise commands.BotMissingPermissions(['administrator'])
        return

    bRole = discord.utils.get(ctx.guild.roles, name=bot.user.name)
    if bRole is None:
        await ctx.message.delete()
        embed = discord.Embed(title="⚠️ Le rôle du bot n'a pas été trouvé !",
                              description="Merci de le renommer en `GuildEdit PRO`.", color=0xe0db01)
        response = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        await response.delete()
        return

    if bRole.position != len(ctx.guild.roles) - 1:
        await ctx.message.delete()
        embed = discord.Embed(title="⚠️ Le rôle du bot n'est pas le plus !",
                              description="Merci de le déplacer tout en haut.", color=0xe0db01)
        response = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        await response.delete()
        return

    path = "./backups/{}/".format(str(ctx.author.id))
    if not exists(path):
        await ctx.send(embed=embed_error("Fichier introuvable.", True))
        return

    if not isfile(join(path, backup_name + ".json")):
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    g = get_backup_dict(join(path, backup_name + ".json"))

    embed_confirmation = discord.Embed(title=":cd::package: Charger cette sauvegarde ?",
                                       description="Vous êtes sur le point de recréer le serveur de cette sauvegarde, **{}**, sur celui-ci.\nLe serveur actuel sera écrasé. Cette action définitive.\nÊtes vous sûr ?".format(
                                           g["name"]), color=0xff0000)
    confirm = await ctx.send(embed=embed_confirmation)
    await confirm.add_reaction(emoji='✅')

    def check(reaction, user):
        return user == ctx.message.author and str(reaction.emoji) == '✅'

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(":x: Délai d'atente dépassé, veuillez retaper la commande.")
        return

    try:
        await clean_guild(ctx.guild)
        await load_backup(join(path, backup_name + ".json"), ctx.guild, "Chargement d'une sauvegarde")
    except Exception as e:
        await ctx.author.send(embed=embed_error(str(e)))
        return


@bot.command()
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 5 * 60, type=commands.BucketType.guild)
@commands.guild_only()
async def loadsettings(ctx, backup_name):
    if not ctx.guild.me.guild_permissions.administrator:
        raise commands.BotMissingPermissions(['administrator'])
        return

    path = "./backups/{}/".format(str(ctx.author.id))
    if not exists(path):
        await ctx.send(embed=embed_error("Fichier introuvable.", True))
        return

    if not isfile(join(path, backup_name + ".json")):
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    g = get_backup_dict(join(path, backup_name + ".json"))

    embed_confirmation = discord.Embed(title=":tools::package: Charger les paramètres ?",
                                       description="Vous êtes sur le point de charger les paramètres de cette sauvegarde (serveur : **{}**) sur ce serveur.\nLes paramètres du serveur actuel seront écrasé. Cette action est définitive.\nÊtes vous sûr ?".format(
                                           g["name"]), color=0xff0000)
    confirm = await ctx.send(embed=embed_confirmation)
    await confirm.add_reaction(emoji='✅')

    def check(reaction, user):
        return user == ctx.message.author and str(reaction.emoji) == '✅'

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(":x: Délai d'atente dépassé, veuillez retaper la commande.")
        return

    action_reason = "Chargement des paramètres de la sauvegarde"
    try:
        guild_icon = None
        try:
            async with aiohttp.ClientSession() as ses:
                async with ses.get(g["icon"]) as r:
                    guild_icon = await r.read()
        except Exception:
            pass

        await ctx.guild.edit(name=g["name"],
                             icon=guild_icon,
                             region=discord.VoiceRegion(g["region"]),
                             afk_channel=[x for x in ctx.guild.voice_channels if x.name == g["afk_channel"]][0] if g[
                                 "afk_channel"] else None,
                             afk_timeout=g["afk_timeout"],
                             verification_level=discord.VerificationLevel(g["verification_level"]),
                             default_notifications=discord.NotificationLevel.only_mentions if g[
                                                                                                  "default_notifications"] == "only_mentions" else discord.NotificationLevel.all_messages,
                             explicit_content_filter=discord.ContentFilter(g["explicit_content_filter"]),
                             system_channel=[x for x in ctx.guild.text_channels if x.name == g["system_channel"]][0] if
                             g["system_channel"] else None,
                             reason=action_reason)
    except Exception as e:
        await ctx.send(embed=embed_error(str(e)))
        return

    embed = discord.Embed(title="✅ Voilà !", description="Les paramètres ont été importés avec succès.",
                          color=0x008040)
    await ctx.send(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 5 * 60, type=commands.BucketType.guild)
@commands.guild_only()
async def loadroles(ctx, backup_name):
    if not ctx.guild.me.guild_permissions.administrator:
        raise commands.BotMissingPermissions(['administrator'])
        return

    bRole = discord.utils.get(ctx.guild.roles, name=bot.user.name)
    if bRole is None:
        await ctx.message.delete()
        embed = discord.Embed(title="⚠️ Le rôle du bot n'a pas été trouvé !",
                              description="Merci de le renommer en `GuildEdit PRO`.", color=0xe0db01)
        response = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        await response.delete()
        return

    if bRole.position != len(ctx.guild.roles) - 1:
        await ctx.message.delete()
        embed = discord.Embed(title="⚠️ Le rôle du bot n'est pas le plus !",
                              description="Merci de le déplacer tout en haut.", color=0xe0db01)
        response = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        await response.delete()
        return

    path = "./backups/{}/".format(str(ctx.author.id))
    if not exists(path):
        await ctx.send(embed=embed_error("Fichier introuvable.", True))
        return

    if not isfile(join(path, backup_name + ".json")):
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    g = get_backup_dict(join(path, backup_name + ".json"))

    embed_confirmation = discord.Embed(title=":triangular_flag_on_post::package: Charger les rôles ?",
                                       description="Vous êtes sur le point de charger les rôles de cette sauvegarde (serveur : **{}**) sur ce serveur.\nLes rôles du serveur actuel seront écrasé. Cette action est définitive.\nÊtes vous sûr ?".format(
                                           g["name"]), color=0xff0000)
    confirm = await ctx.send(embed=embed_confirmation)
    await confirm.add_reaction(emoji='✅')

    def check(reaction, user):
        return user == ctx.message.author and str(reaction.emoji) == '✅'

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(":x: Délai d'atente dépassé, veuillez retaper la commande.")
        return

    action_reason = "Chargement des rôles de la sauvegarde"
    try:
        for i in range(round(len(ctx.guild.roles) / 2)):
            for role in ctx.guild.roles:
                try:
                    await role.delete(reason=action_reason)
                except Exception:
                    pass

        for role in g["roles"][::-1]:
            permissions = discord.Permissions()
            permissions.update(**dict(role["permissions"]))
            if role["name"] != "@everyone":
                await ctx.guild.create_role(name=role["name"], colour=discord.Colour.from_rgb(*role["colour"]),
                                            hoist=role["hoist"], mentionable=role["mentionable"],
                                            permissions=permissions, reason=action_reason)
            else:
                await ctx.guild.default_role.edit(permissions=permissions, reason=action_reason)
    except Exception as e:
        await ctx.send(embed=embed_error(str(e)))
        return

    embed = discord.Embed(title="✅ Voilà !", description="Les rôles ont été importés avec succès.", color=0x008040)
    await confirm.clear_reactions()
    await confirm.edit(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 5 * 60, type=commands.BucketType.guild)
@commands.guild_only()
async def loadchannels(ctx, backup_name):
    if not ctx.guild.me.guild_permissions.administrator:
        raise commands.BotMissingPermissions(['administrator'])
        return

    path = "./backups/{}/".format(str(ctx.author.id))
    if not exists(path):
        await ctx.send(embed=embed_error("Fichier introuvable.", True))
        return

    if not isfile(join(path, backup_name + ".json")):
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    g = get_backup_dict(join(path, backup_name + ".json"))

    embed_confirmation = discord.Embed(title=":speech_balloon::speaker::package: Charger les salons ?",
                                       description="Vous êtes sur le point de charger les salons de cette sauvegarde (serveur : **{}**) sur ce serveur.\nLes salons du serveur actuel seront écrasé. Cette action est définitive.\nÊtes vous sûr ?".format(
                                           g["name"]), color=0xff0000)
    confirm = await ctx.send(embed=embed_confirmation)
    await confirm.add_reaction(emoji='✅')

    def check(reaction, user):
        return user == ctx.message.author and str(reaction.emoji) == '✅'

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(":x: Délai d'atente dépassé, veuillez retaper la commande.")
        return

    action_reason = "Chargement des salons de la sauvegarde"
    try:
        for channel in ctx.guild.channels:
            await channel.delete(reason=action_reason)

        for category in g["categories"]:
            new_cat = await ctx.guild.create_category(category["name"], reason=action_reason)

        for channel in g["text_channels"]:
            category = None
            try:
                category = [x for x in ctx.guild.categories if x.name == channel["category"]][0]
            except:
                pass
            new_chan = await ctx.guild.create_text_channel(channel["name"], reason=action_reason)
            await new_chan.edit(topic=channel["topic"], nsfw=channel["nsfw"], category=category,
                                slowmode_delay=channel["slowmode_delay"], reason=action_reason)

        for channel in g["voice_channels"]:
            category = None
            try:
                category = [x for x in ctx.guild.categories if x.name == channel["category"]][0]
            except:
                pass
            new_chan = await ctx.guild.create_voice_channel(channel["name"], reason=action_reason)
            await new_chan.edit(
                channel["bitrate"] if channel["bitrate"] <= 96000 and channel["bitrate"] >= 8000 else 64000,
                user_limit=channel["user_limit"], category=category, reason=action_reason)

        for channel in g["text_channels"]:
            await [x for x in ctx.guild.text_channels if x.name == channel["name"]][0].edit(
                position=channel["position"] if channel["position"] < len(ctx.guild.text_channels) else len(
                    ctx.guild.text_channels) - 1, reason=action_reason)

        for channel in g["voice_channels"]:
            await [x for x in ctx.guild.voice_channels if x.name == channel["name"]][0].edit(
                position=channel["position"] if channel["position"] < len(ctx.guild.voice_channels) else len(
                    ctx.guild.voice_channels) - 1, reason=action_reason)

        for category in g["categories"]:
            await [x for x in ctx.guild.categories if x.name == category["name"]][0].edit(
                position=category["position"] if category["position"] < len(ctx.guild.categories) else len(
                    ctx.guild.categories) - 1, reason=action_reason)
    except Exception as e:
        await ctx.message.author.send(embed=embed_error(str(e)))
        return

    embed = discord.Embed(title="✅ Voilà !", description="Les salons ont été importés avec succès.", color=0x008040)
    await ctx.guild.text_channels[0].send(content=ctx.message.author.mention, embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 5 * 60, type=commands.BucketType.guild)
@commands.guild_only()
async def loadbans(ctx, backup_name):
    if not ctx.guild.me.guild_permissions.administrator:
        raise commands.BotMissingPermissions(['administrator'])
        return

    path = "./backups/{}/".format(str(ctx.author.id))
    if not exists(path):
        await ctx.send(embed=embed_error("Fichier introuvable.", True))
        return

    if not isfile(join(path, backup_name + ".json")):
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    g = get_backup_dict(join(path, backup_name + ".json"))

    embed_confirmation = discord.Embed(title=":no_entry::package: Charger les bannissements ?",
                                       description="Vous êtes sur le point de charger les bannissements de cette sauvegarde (serveur : **{}**) sur ce serveur.\nLes bannissements du serveur actuel seront écrasé. Cette action est définitive.\nÊtes vous sûr ?".format(
                                           g["name"]), color=0xff0000)
    confirm = await ctx.send(embed=embed_confirmation)
    await confirm.add_reaction(emoji='✅')

    def check(reaction, user):
        return user == ctx.message.author and str(reaction.emoji) == '✅'

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(":x: Délai d'atente dépassé, veuillez retaper la commande.")
        return

    action_reason = "Chargement des bannissements de la sauvegarde"
    try:
        guild_bans = [ban_entry[1] for ban_entry in await ctx.guild.bans()]
        backup_bans = []
        backup_reasons = []
        for ban_entry in g["bans"]:
            try:
                user = await bot.fetch_user(ban_entry["id"])
                backup_bans.append(user)
                backup_reasons.append(ban_entry["reason"])
            except Exception:
                pass

        for user in guild_bans:
            if not user in backup_bans:
                try:
                    await ctx.guild.unban(user, reason=action_reason)
                except Exception:
                    pass

        for user in backup_bans:
            if not user in guild_bans:
                try:
                    await ctx.guild.ban(user=user, reason=backup_reasons[backup_bans.index(user)])
                except Exception:
                    pass
    except Exception as e:
        await ctx.send(embed=embed_error(str(e)))
        return

    embed = discord.Embed(title="✅ Voilà !", description="Les bannissements ont été importés avec succès.",
                          color=0x008040)
    await confirm.clear_reactions()
    await confirm.edit(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 5 * 60, type=commands.BucketType.guild)
@commands.guild_only()
async def loadmembers(ctx, backup_name):
    if not ctx.guild.me.guild_permissions.administrator:
        raise commands.BotMissingPermissions(['administrator'])
        return

    path = "./backups/{}/".format(str(ctx.author.id))
    if not exists(path):
        await ctx.send(embed=embed_error("Fichier introuvable.", True))
        return

    if not isfile(join(path, backup_name + ".json")):
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    g = get_backup_dict(join(path, backup_name + ".json"))

    embed_confirmation = discord.Embed(title=":man::package: Charger les membres ?",
                                       description="Vous êtes sur le point de charger les membres de cette sauvegarde (serveur : **{}**) sur ce serveur.\nLes rôles et pseudos des membres actuels du serveur seront écrasé. Cette action est définitive.\nÊtes vous sûr ?".format(
                                           g["name"]), color=0xff0000)
    confirm = await ctx.send(embed=embed_confirmation)
    await confirm.add_reaction(emoji='✅')

    def check(reaction, user):
        return user == ctx.message.author and str(reaction.emoji) == '✅'

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(":x: Délai d'atente dépassé, veuillez retaper la commande.")
        return

    action_reason = "Chargement des membres de la sauvegarde"
    for member in g["members"]:
        guild_member = ctx.guild.get_member(int(member["id"]))
        if guild_member is not None and guild_member != ctx.guild.me:
            if "nick" in member and guild_member != ctx.guild.owner and guild_member.nick != member["nick"]:
                try:
                    await guild_member.edit(nick=member["nick"], reason=action_reason)
                except Exception:
                    pass

            if len(guild_member.roles) != 1:
                continue

            member_roles = [discord.utils.get(ctx.guild.roles, name=role_name) for role_name in member["roles"]]
            member_roles = [m_r for m_r in member_roles if m_r is not None and not m_r.managed]
            for role in member_roles:
                try:
                    await guild_member.add_roles(role, reason=action_reason)
                except Exception:
                    pass


    embed = discord.Embed(title="✅ Voilà !", description="Les membres ont été importés avec succès.", color=0x008040)
    await confirm.clear_reactions()
    await confirm.edit(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 5 * 60, type=commands.BucketType.guild)
@commands.guild_only()
async def loademojis(ctx, backup_name):
    if not ctx.guild.me.guild_permissions.administrator:
        raise commands.BotMissingPermissions(['administrator'])
        return

    path = "./backups/{}/".format(str(ctx.author.id))
    if not exists(path):
        await ctx.send(embed=embed_error("Fichier introuvable.", True))
        return

    if not isfile(join(path, backup_name + ".json")):
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    g = get_backup_dict(join(path, backup_name + ".json"))

    embed_confirmation = discord.Embed(title=":smile::package: Charger les emojis ?",
                                       description="Vous êtes sur le point de charger les emojis de cette sauvegarde (serveur : **{}**) sur ce serveur.\nLes emojis du serveur actuel seront écrasé. Cette action est définitive.\nÊtes vous sûr ?".format(
                                           g["name"]), color=0xff0000)
    confirm = await ctx.send(embed=embed_confirmation)
    await confirm.add_reaction(emoji='✅')

    def check(reaction, user):
        return user == ctx.message.author and str(reaction.emoji) == '✅'

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(":x: Délai d'atente dépassé, veuillez retaper la commande.")
        return

    action_reason = "Chargement des emojis de la sauvegarde"
    try:
        backup_emojis = [emoji["name"] for emoji in g["emojis"]]
        for emoji in ctx.guild.emojis:
            if not emoji.name in backup_emojis:
                await emoji.delete(reason=action_reason)

        guild_emojis = [emoji.name for emoji in ctx.guild.emojis]
        for emoji in g["emojis"]:
            if emoji["name"] in guild_emojis:
                continue

            try:
                img = None
                async with aiohttp.ClientSession() as ses:
                    async with ses.get(emoji["url"]) as r:
                        img = await r.read()
                await ctx.guild.create_custom_emoji(name=emoji["name"], image=img, reason=action_reason)
            except Exception:
                pass
    except Exception as e:
        await ctx.send(embed=embed_error(str(e)))
        return

    embed = discord.Embed(title="✅ Voilà !", description="Les emojis ont été importés avec succès.", color=0x008040)
    await confirm.clear_reactions()
    await confirm.edit(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 3 * 60, type=commands.BucketType.guild)
@commands.guild_only()
async def createbackup(ctx):
    if not ctx.guild.me.guild_permissions.administrator:
        raise commands.BotMissingPermissions(['administrator'])
        return

    path = "./backups/{}/".format(str(ctx.author.id))
    if not exists(path):
        makedirs(path)
    fcount = len([f for f in listdir(path) if isfile(join(path, f))])

    embed_confirmation = discord.Embed(title=":inbox_tray::package: Créer une sauvegarde ?",
                                       color=0xff8000)
    confirm = await ctx.send(embed=embed_confirmation)
    await confirm.add_reaction(emoji='✅')

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) == '✅'

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(":x: Délai d'atente dépassé, veuillez retaper la commande.")
        return

    try:
        await create_backup("{}{}.json".format(path, get_filename(ctx.guild.id)), ctx.guild)
    except Exception as e:
        await ctx.send(embed=embed_error(str(e)))
        return

    await confirm.clear_reactions()
    embed = discord.Embed(title="✅ Voilà !", description="Votre sauvegarde a été créée avec succès.",
                          color=0x008040)
    await confirm.edit(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 3 * 60, type=commands.BucketType.guild)
@commands.guild_only()
async def updatebackup(ctx, backup_name):
    if not ctx.guild.me.guild_permissions.administrator:
        raise commands.BotMissingPermissions(['administrator'])
        return

    path = "./backups/{}/".format(str(ctx.author.id))
    if not exists(path):
        await ctx.send(embed=embed_error("Fichier introuvable.", True))
        return

    if not isfile(join(path, backup_name + ".json")):
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    embed_confirmation = discord.Embed(title=":inbox_tray::package: Mettre à jour `{}` ?".format(backup_name),
                                       description="Attention, cette sauvegarde sera écrasée. Une nouvelle sauvegarde va remplacer celle-ci.\nÊtes-vous sûr ?",
                                       color=0xff8000)
    confirm = await ctx.send(embed=embed_confirmation)
    await confirm.add_reaction(emoji='✅')

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) == '✅'

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(":x: Délai d'atente dépassé, veuillez retaper la commande.")
        return

    try:
        await create_backup(join(path, backup_name + ".json"), ctx.guild)
    except Exception as e:
        await ctx.send(embed=embed_error(str(e)))
        return

    await confirm.clear_reactions()
    embed = discord.Embed(title="✅ Voilà !", description="Votre sauvegarde a été mise à jour avec succès.",
                          color=0x008040)
    await confirm.edit(embed=embed)


@bot.command()
@commands.cooldown(1, 2 * 60, type=commands.BucketType.user)
async def backuplist(ctx):
    path = "./backups/{}/".format(str(ctx.author.id))
    if not exists(path):
        await ctx.send(embed=embed_error("Aucune sauvegarde disponible.", True))
        return

    file_list = [f for f in listdir(path) if isfile(join(path, f))]
    if len(file_list) == 0:
        await ctx.send(embed=embed_error("Aucune sauvegarde disponible.", True))
        return

    strf_list = "**Nombre de sauvegardes : {}**\n```\n".format(str(len(file_list)))
    for f in file_list:
        strf_list += f.replace(".json", "") + "\n"
    strf_list += "```"

    embed = discord.Embed(title=":package: Liste des sauvegardes", description=strf_list, color=0x008080)
    await ctx.send(embed=embed)


@bot.command()
@commands.cooldown(2, 3 * 60, type=commands.BucketType.user)
async def renamebackup(ctx, backup_name, new_name):
    path = "./backups/{}/".format(str(ctx.author.id))
    if not exists(path):
        await ctx.send(embed=embed_error("Fichier introuvable.", True))
        return

    if not isfile(join(path, backup_name + ".json")):
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    new_name = format_name(new_name)
    if len(new_name) < 1 or len(new_name) > 50:
        await ctx.send(
            embed=embed_error("Nom invalide. Il doit comporter entre 1 et 50 caractères, non spéciaux.", True))
        return

    used_names = [f.replace('.json', '') for f in listdir(path) if isfile(join(path, f))]
    if new_name in used_names:
        await ctx.send(
            embed=embed_error("Nom déjà utilisé !", True))
        return

    embed_confirmation = discord.Embed(title=":pen_ballpoint::package: Renommer cette sauvegarde ?",
                                       description="`{}` sera renommée en `{}`.\nÊtes vous sûr ?".format(backup_name,
                                                                                                         new_name),
                                       color=0xff8000)
    confirm = await ctx.send(embed=embed_confirmation)
    await confirm.add_reaction(emoji='✅')

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) == '✅'

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(":x: Délai d'atente dépassé, veuillez retaper la commande.")
        return

    rename(join(path, backup_name + ".json"), join(path, new_name + ".json"))

    try:
        await confirm.clear_reactions()
    except Exception:
        pass

    embed = discord.Embed(title="✅ Succès.", description="Votre sauvegarde a bien été renommée.", color=0x008040)
    await confirm.edit(embed=embed)


@bot.command()
@commands.cooldown(2, 3 * 60, type=commands.BucketType.user)
async def deletebackup(ctx, backup_name):
    path = "./backups/{}/".format(str(ctx.author.id))
    if not exists(path):
        await ctx.send(embed=embed_error("Fichier introuvable.", True))
        return

    if not isfile(join(path, backup_name + ".json")):
        await ctx.send(embed=embed_error("Fichier introuvable."))
        return

    embed_confirmation = discord.Embed(title=":outbox_tray::package: Supprimer cette sauvegarde ?",
                                       description="`{}` sera supprimée définitivement.\nÊtes vous sûr ?".format(
                                           backup_name),
                                       color=0xff0000)
    confirm = await ctx.send(embed=embed_confirmation)
    await confirm.add_reaction(emoji='✅')

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) == '✅'

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(":x: Délai d'atente dépassé, veuillez retaper la commande.")
        return

    remove(join(path, backup_name + ".json"))

    try:
        await confirm.clear_reactions()
    except Exception:
        pass

    embed = discord.Embed(title="✅ Succès.", description="Votre sauvegarde a bien été supprimée.", color=0x008040)
    await confirm.edit(embed=embed)


bot.run(bot_token, bot=True, reconnect=True)