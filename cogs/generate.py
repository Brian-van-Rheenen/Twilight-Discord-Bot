import discord
import re
import datetime
import time
import itertools
import math
import locale

from cogs.maincog import Maincog
from discord.utils import get
from discord.ext import commands
from db import dbconnection as dbc

locale.setlocale(locale.LC_ALL, '')

class Generate(Maincog):

    def __init__(self, client):
        Maincog.__init__(self, client)
        self.dbc = dbc.DBConnection()
        self.teamEmoji = "\U0001F1F9"
        self.cancelEmoji = "\U0000274C"
        self.doneEmoji = "\U00002705"
        self.tankRoles = [
            "Druid",
            "Monk",
            "Demon Hunter",
            "Paladin",
            "Warrior",
            "Death Knight",
            "Leather",
            "Plate"
        ]
        self.healerRoles = [
            "Druid",
            "Monk",
            "Paladin",
            "Priest",
            "Shaman",
            "Cloth",
            "Leather",
            "Mail",
            "Plate"
        ]

    @commands.Cog.listener()
    async def on_ready(self):
        self.completedChannel = self.client.get_channel(731479403862949928)
        self.tankEmoji = self.client.get_emoji(714930608266018859)
        self.healerEmoji = self.client.get_emoji(714930600267612181)
        self.dpsEmoji = self.client.get_emoji(714930578461425724)
        self.keystoneEmoji = self.client.get_emoji(715918950092898346)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if self.checkIfUserIsItself(payload.member): return
        user = payload.member
        channel = self.client.get_channel(payload.channel_id)
        if not channel: return
        if isinstance(channel, discord.DMChannel): return

        if "boosts" not in channel.name: return
        message = await channel.fetch_message(payload.message_id)

        if not message.embeds: return
        id = message.id
        guild = self.client.get_guild(payload.guild_id)

        if self.helper.getRole(guild, "M+ Banned") in user.roles:
            await channel.send(f"\U0001F6AB {user.mention}, you are currently Mythic+ banned and therefore not allowed to sign up. \U0001F6AB")
            await message.remove_reaction(payload.emoji, user)
            return

        groupQuery = f"SELECT * FROM mythicplus.group WHERE id = '{id}'"
        group = self.dbc.select(groupQuery)

        if group is None: return
        author = group["advertiser"]
        author = author.split(" ", 1)[0]

        if group["created"]:
            if str(payload.emoji) == str(self.doneEmoji) and user.mention == author:
                if "horde" in channel.name:
                    faction = "H"
                elif "alliance" in channel.name:
                    faction = "A"

                gold_pot = group["gold_pot"]
                if "k" in gold_pot:
                    gold_pot = gold_pot.replace('k', '')
                    gold_pot = str(gold_pot) + "000"

                usernameRegex = "<@.*?>"
                nicknameRegex = "<@!.*?>"
                party = re.compile("(%s|%s)" % (usernameRegex, nicknameRegex)).findall(message.embeds[0].description)

                ctx = await self.client.get_context(message)
                ctx.author = get(ctx.guild.members, mention=author)
                result = await ctx.invoke(self.client.get_command('completed'), 'M+', gold_pot, f"{group['payment_realm']}-{faction}", author, party[0], party[1], party[2], party[3])

                if result[0]:
                    await channel.send(f"{self.doneEmoji} Succesfully added the Mythic+ run to the sheets!\n"
                                       f"Group id: {id}\n"
                                       f"{result[1].jump_url}")
                else:
                    await result[1].delete()
                    await channel.send(f"{self.cancelEmoji} Something went wrong when trying to add the Mythic+ run to the sheets. Please add it manually in {self.completedChannel.mention}\n"
                                       f"Group id: {id}")

            return

        additionalRolesQuery = f"SELECT `role` FROM mythicplus.group_additional_roles WHERE groupid = '{id}'"
        group["additional_roles"] = self.dbc.select(additionalRolesQuery, True)

        if str(payload.emoji) == str(self.tankEmoji):
            data = {"user": user, "faction": group["faction"], "armor_type": group["armor_type"], "keystone_level": group["keystone_level"], "role": "Tank", "additional_roles": group["additional_roles"]}
            if not await self.checkRoles(guild, channel, data):
                await message.remove_reaction(payload.emoji, user)
                return

            role = "Tank"

        if str(payload.emoji) == str(self.healerEmoji):
            data = {"user": user, "faction": group["faction"], "armor_type": group["armor_type"], "keystone_level": group["keystone_level"], "role": "Healer", "additional_roles": group["additional_roles"]}
            if not await self.checkRoles(guild, channel, data):
                await message.remove_reaction(payload.emoji, user)
                return

            role = "Healer"

        if str(payload.emoji) == str(self.dpsEmoji):
            data = {"user": user, "faction": group["faction"], "armor_type": group["armor_type"], "keystone_level": group["keystone_level"], "role": "Damage", "additional_roles": group["additional_roles"]}
            if not await self.checkRoles(guild, channel, data):
                await message.remove_reaction(payload.emoji, user)
                return

            role = "Damage"

        if str(payload.emoji) == str(self.tankEmoji) or str(payload.emoji) == str(self.healerEmoji) or str(payload.emoji) == str(self.dpsEmoji):
            query = f"""INSERT INTO mythicplus.booster (groupid, `user`, `role`)
                       VALUES ('{id}', '{user.mention}', '{role}')"""
            self.dbc.insert(query)

        if str(payload.emoji) == str(self.keystoneEmoji):
            existsQuery = f"SELECT EXISTS(SELECT 1 FROM mythicplus.booster WHERE groupid = '{id}' AND user = '{user.mention}') as 'result'"
            existsInBooster = self.dbc.select(existsQuery)
            if existsInBooster["result"]:
                query = f"""INSERT INTO mythicplus.keystone (groupid, `user`, `has_keystone`)
                            SELECT '{id}', '{user.mention}', 1 FROM DUAL
                            WHERE NOT EXISTS (SELECT groupid, `user` FROM mythicplus.keystone
                                    WHERE groupid = '{id}' AND `user` = '{user.mention}')"""
                self.dbc.insert(query)
            else:
                await message.remove_reaction(payload.emoji, user)
                await channel.send(f"{user.mention}, assign yourself a role before marking yourself as a keystone holder.")
                return

        if str(payload.emoji) == str(self.tankEmoji) or str(payload.emoji) == str(self.healerEmoji) or str(payload.emoji) == str(self.dpsEmoji) or str(payload.emoji) == str(self.keystoneEmoji):
            await self.updateGroup(message)

        if str(payload.emoji) == str(self.teamEmoji):
            data = {"user": user, "faction": group["faction"], "armor_type": group["armor_type"], "keystone_level": group["keystone_level"], "role": "All", "team": True, "additional_roles": group["additional_roles"]}
            if not await self.checkRoles(guild, channel, data):
                await message.remove_reaction(payload.emoji, user)
                return

            existsInBoosterQuery = f"SELECT EXISTS(SELECT 1 FROM mythicplus.booster WHERE groupid = '{id}' AND user = '{user.mention}') as 'result'"
            existsInKeystoneQuery = f"SELECT EXISTS(SELECT 1 FROM mythicplus.keystone WHERE groupid = '{id}' AND user = '{user.mention}') as 'result'"
            existsInBooster = self.dbc.select(existsInBoosterQuery)
            existsInKeystone = self.dbc.select(existsInKeystoneQuery)

            if not existsInBooster["result"]:
                query = f"""INSERT INTO mythicplus.booster (groupid, `user`, `role`, is_teamleader)
                           VALUES ('{id}', '{user.mention}', 'All', '1')"""
                self.dbc.insert(query)
            else:
                query = f"""UPDATE mythicplus.booster
                        SET `role` = 'All', is_teamleader = 1
                        WHERE groupid = %s AND user = %s"""
                value = (id, user.mention)
                self.dbc.insert(query, value)

            if not existsInKeystone["result"]:
                query = f"""INSERT INTO mythicplus.keystone (groupid, `user`, has_keystone)
                           SELECT '{id}', '{user.mention}', 1 FROM DUAL
                           WHERE NOT EXISTS (SELECT groupid, `user` FROM mythicplus.keystone
                                    WHERE groupid = '{id}' AND `user` = '{user.mention}')"""
                self.dbc.insert(query)
            else:
                query = f"""UPDATE mythicplus.keystone
                        SET has_keystone = 1
                        WHERE groupid = %s AND user = %s"""
                value = (id, user.mention)
                self.dbc.insert(query, value)

            group = [user.mention, user.mention, user.mention, user.mention, user.mention]
            await self.createGroup(message, group, team=True)
            return

        if str(payload.emoji) == str(self.cancelEmoji):
            if user.mention == author:
                await message.delete() #TODO: remove from database?
                await self.cancelGroup(message)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        channel = self.client.get_channel(payload.channel_id)
        if not channel: return
        if isinstance(channel, discord.DMChannel): return #from completed
        guild = self.client.get_guild(payload.guild_id)
        user = guild.get_member(payload.user_id)
        if self.checkIfUserIsItself(user): return

        if "boosts" not in channel.name: return
        message = await channel.fetch_message(payload.message_id)

        if not message.embeds: return
        id = message.id

        query = f"SELECT * FROM mythicplus.group WHERE id = '{id}'"
        group = self.dbc.select(query)
        if group is None or group["created"]: return

        if str(payload.emoji) == str(self.tankEmoji):
            role = "Tank"

        if str(payload.emoji) == str(self.healerEmoji):
            role = "Healer"

        if str(payload.emoji) == str(self.dpsEmoji):
            role = "Damage"

        if str(payload.emoji) == str(self.tankEmoji) or str(payload.emoji) == str(self.healerEmoji) or str(payload.emoji) == str(self.dpsEmoji):
            query = f"""DELETE FROM mythicplus.booster WHERE groupid = '{id}' AND user = '{user.mention}' AND role = '{role}'"""
            self.dbc.delete(query)

        if str(payload.emoji) == str(self.keystoneEmoji):
            query = f"""DELETE FROM mythicplus.keystone WHERE groupid = '{id}' AND user = '{user.mention}'"""
            self.dbc.delete(query)

        if str(payload.emoji) == str(self.tankEmoji) or str(payload.emoji) == str(self.healerEmoji) or str(payload.emoji) == str(self.dpsEmoji) or str(payload.emoji) == str(self.keystoneEmoji):
            await self.updateGroup(message)

    @commands.command()
    @commands.has_any_role("Trainee Advertiser", "Advertiser", "Management", "Council")
    async def generate(self, ctx):
        msg = ctx.message.content[10:]
        result = [x.strip() for x in re.split(' ', msg)]
        channel = ctx.message.channel.name

        if "horde" in channel:
            faction = "Horde"
        elif "alliance" in channel:
            faction = "Alliance"

        if len(result) >= 6:
            keystone = result[2]
            keystoneLevel = int(keystone.partition("+")[2])
            mentions = ""
            result[5] = result[5].capitalize()
            armor = result[5]

            if result[5] != "Any":
                if not self.helper.containsRoleMention(result[5]):
                    armor = self.helper.getRole(ctx.guild, result[5]).mention

            advertiserNote = ""
            additionalRoles = []
            if keystoneLevel < 18:
                for x in range(6, len(result)):
                    if self.helper.containsRoleMention(result[x]):
                        mentions += result[x] + " "
                        additionalRoles.append(result[x])
                    else:
                        advertiserNote += result[x] + " "

            if not additionalRoles:
                if keystoneLevel < 18 and result[5] != "Any":
                    if result[5] == "Cloth" or result[5] == "Mail":
                        tankRole = self.helper.getRole(ctx.guild, "Tank").mention
                        mentions += tankRole + " "

                    mentions += armor + " "
                else:
                    armor = "Any"

                    if keystoneLevel >= 18:
                        keystoneRole = self.helper.getRole(ctx.guild, "Legendary").mention
                        mentions += keystoneRole + " "
                    else:
                        if keystoneLevel >= 15 and keystoneLevel < 18:
                            if faction == "Horde":
                                keystoneRole = self.helper.getRole(ctx.guild, "Highkey Booster Horde").mention
                            elif faction == "Alliance":
                                keystoneRole = self.helper.getRole(ctx.guild, "Highkey Booster Alliance").mention
                            mentions += keystoneRole + " "
                        elif keystoneLevel >= 10 and keystoneLevel <= 14:
                            keystoneRole = self.helper.getRole(ctx.guild, "Mplus Booster").mention
                            mentions += keystoneRole + " "

                        tankRole = self.helper.getRole(ctx.guild, "Tank").mention
                        healerRole = self.helper.getRole(ctx.guild, "Healer").mention
                        damageRole = self.helper.getRole(ctx.guild, "Damage").mention
                        mentions += tankRole + " " + healerRole + " " + damageRole + " "

            advertiser = f"{ctx.message.author.mention} ({result[0]})"
            result[3] = result[3].lower()

            if "k" in result[3]:
                goldPot = result[3].replace('k', '')
                goldPot = str(goldPot) + "000"
            else:
                goldPot = result[3]
            boosterCut = math.ceil((int(goldPot) / 100) * 17.8)

            embed = discord.Embed(title=f"Generating {result[2]} run!", description="Click on the reaction below the post with your assigned roles to join the group.\n" +
                                        "First come first served **but** the bot will **prioritise** a keyholder over those who do not have one.\n", color=0x5cf033)
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/632628531528073249/644669381451710495/TwilightDiscIocn.jpg")
            embed.add_field(name="Gold Pot", value=result[3], inline=True)
            embed.add_field(name="Booster Cut", value=f"{boosterCut:n}", inline=True)
            embed.add_field(name="Payment Realm", value=result[1], inline=True)
            embed.add_field(name="Keystone Level", value=result[2], inline=True)
            embed.add_field(name="Dungeon", value=result[4], inline=True)
            embed.add_field(name="Armor Type", value=armor, inline=True)
            embed.add_field(name="Advertiser", value=advertiser)

            if advertiserNote:
                embed.add_field(name="Advertiser Note", value=advertiserNote, inline=False)

            msg = await ctx.message.channel.send(content=mentions, embed=embed)
            embed.set_footer(text=f"Group id: {msg.id}.")
            await msg.edit(embed=embed)

            query = """INSERT INTO mythicplus.group (id, title, description, faction, payment_realm, gold_pot, booster_cut, keystone_level, dungeon, armor_type, advertiser, advertiser_note, footer)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            values = (msg.id, embed.title, embed.description, faction, result[1], result[3], boosterCut, result[2], result[4], armor, advertiser, advertiserNote, embed.footer.text)
            self.dbc.insert(query, values)

            if additionalRoles:
                query = "INSERT INTO mythicplus.group_additional_roles (groupid, role) VALUES "
                for additionalRole in additionalRoles:
                    query += f"('{msg.id}', '{additionalRole}'), "

                self.dbc.insert(query[:-2])

            # Tank
            await msg.add_reaction(self.tankEmoji)

            # Healer
            await msg.add_reaction(self.healerEmoji)

            # DPS
            await msg.add_reaction(self.dpsEmoji)

            # Keystones
            await msg.add_reaction(self.keystoneEmoji)

            # Team
            await msg.add_reaction(self.teamEmoji)

            # Cancel
            await msg.add_reaction(self.cancelEmoji)

            await ctx.message.delete()

        else:
            # Needs more/less fields
            await ctx.message.channel.send(':x: The command you have entered is invalid. Please check if the command you entered is valid. :x:', delete_after=10.0)

    async def cancelGroup(self, message):
        group = list(dict.fromkeys(self.getGroup(message)))
        mentions = ""

        for i in range(len(group)):
            mentions += group[i]

        if mentions:
            createdMessage = (f"{mentions}\n" +
                      f"Your group was cancelled by the advertiser.\n")
            await message.channel.send(createdMessage)

    async def updateGroup(self, message):
        group = self.getGroup(message)
        tank = group[0]
        healer = group[1]
        dpsOne = group[2]
        dpsTwo = group[3]
        keystone = group[4]

        if tank and healer and dpsOne and dpsTwo and keystone:
            await self.createGroup(message, group)
            return

        embed = message.embeds[0]
        embed.description = f"""Click on the reaction below the post with your assigned roles to join the group. First come first serve.\n
                            {self.tankEmoji} {tank}\n{self.healerEmoji} {healer}\n{self.dpsEmoji} {dpsOne}\n{self.dpsEmoji} {dpsTwo}\n\n{self.keystoneEmoji} {keystone}"""
        await message.edit(embed=embed)

    def getGroup(self, message):
        id = message.id

        allBoostersQuery = f"SELECT * FROM mythicplus.booster WHERE groupid = '{id}'"
        allBoosters = self.dbc.select(allBoostersQuery, True)
        tanks = [booster for booster in allBoosters if booster['role'] == "Tank"]
        healers = [booster for booster in allBoosters if booster['role'] == "Healer"]
        dps = [booster for booster in allBoosters if booster['role'] == "Damage"]
        keystoneQuery = f"SELECT * FROM mythicplus.keystone where groupid = '{id}' AND has_keystone = 1 LIMIT 1;"
        keystone = self.dbc.select(keystoneQuery)
        keystone = "" if keystone == None else keystone['user']

        try:
            keystoneUser = [booster for booster in tanks if booster['user'] == keystone][0]['user']
            role = 'Tank'
        except:
            try:
                keystoneUser = [booster for booster in healers if booster['user'] == keystone][0]['user']
                role = 'Healer'
            except:
                try:
                    keystoneUser = [booster for booster in dps if booster['user'] == keystone][0]['user']
                    role = 'DPS'
                except:
                    keystoneUser = None
                    role = ''

        return self.getBoosters(tanks, healers, dps, keystoneUser, role)

    def getBoosters(self, tanks, healers, dps, keystoneUser, role):
        tank = next((booster['user'] for booster in tanks), "")
        healer = next((booster['user'] for booster in healers if booster['user'] != tank), "")
        try:
            dpsOne = [booster['user'] for booster in dps if booster['user'] != healer and booster['user'] != tank][0]
        except:
            dpsOne = ""
        try:
            dpsTwo = [booster['user'] for booster in dps if booster['user'] != healer and booster['user'] != tank][1]
        except:
            dpsTwo = ""

        if keystoneUser:
            if role == 'Tank':
                tank = keystoneUser
                healer = next((booster['user'] for booster in healers if booster['user'] != keystoneUser and booster['user'] != dpsOne and booster['user'] != dpsTwo), "")
                inDPS = False

            if role == 'Healer':
                tank = next((booster['user'] for booster in tanks if booster['user'] != keystoneUser and booster['user'] != dpsOne and booster['user'] != dpsTwo), "")
                healer = keystoneUser
                inDPS = False

            if role == 'DPS':
                tank = next((booster['user'] for booster in tanks if booster['user'] != keystoneUser and booster['user'] != healer), "")
                healer = next((booster['user'] for booster in healers if booster['user'] != keystoneUser and booster['user'] != tank), "")
                inDPS = True

            if inDPS:
                if dpsOne != keystoneUser:
                    dpsTwo = dpsOne
                    dpsOne = keystoneUser
            else:
                try:
                    dpsOne = [booster['user'] for booster in dps if booster['user'] != keystoneUser and booster['user'] != healer and booster['user'] != tank][0]
                except:
                    dpsOne = ""
                try:
                    dpsTwo = [booster['user'] for booster in dps if booster['user'] != keystoneUser and booster['user'] != healer and booster['user'] != tank][1]
                except:
                    dpsTwo = ""

        keystone = "" if keystoneUser == None else keystoneUser
        group = [tank, healer, dpsOne, dpsTwo, keystone]
        return group

    async def createGroup(self, message, group, team=False):
        query = f"""UPDATE mythicplus.group
                SET created = 1
                WHERE id = {message.id}"""
        self.dbc.insert(query)

        embed = message.embeds[0]

        tank = group[0]
        healer = group[1]
        dpsOne = group[2]
        dpsTwo = group[3]
        keystoneHolder = group[4]

        query = f"SELECT keystone_level FROM mythicplus.group WHERE id = '{message.id}'"
        group = self.dbc.select(query)

        advertiser = re.findall('\(([^)]+)', embed.fields[6].value)[0]

        embed.title = f"Generated {group['keystone_level']} Group"
        embed.description = (f"{self.tankEmoji} {tank}\n{self.healerEmoji} {healer}\n{self.dpsEmoji} {dpsOne}\n{self.dpsEmoji} {dpsTwo}\n\n{self.keystoneEmoji} {keystoneHolder}\n" +
                             f"Please whisper `/w {advertiser} invite`")
        embed.set_footer(text=f"{embed.footer.text} Group created at: {datetime.datetime.now().strftime('%H:%M:%S')}")
        editedmsg = await message.edit(embed=embed)

        mentions = f"{self.teamEmoji} {tank}" if team else f"{self.tankEmoji} {tank} {self.healerEmoji} {healer} {self.dpsEmoji} {dpsOne} {self.dpsEmoji} {dpsTwo}"
        createdMessage = (f"{mentions}\nPlease whisper `/w {advertiser} invite`. See the message above for more details.\n" +
                  f"Group id: {message.id}")
        await message.channel.send(createdMessage)

        reactions = message.reactions
        for reaction in reactions[:]:
            await reaction.clear()

        # Done
        await message.add_reaction(self.doneEmoji)

    async def checkRoles(self, guild, channel, data):
        isValid = False
        keystoneLevel = int(data["keystone_level"].partition("+")[2])

        if keystoneLevel >= 15:
            if data["faction"] == "Horde":
                factionRole = self.helper.getRole(guild, "Highkey Booster Horde")
            elif data["faction"] == "Alliance":
                factionRole = self.helper.getRole(guild, "Highkey Booster Alliance")
        else:
            factionRole = self.helper.getRole(guild, "Mplus Booster")

        if keystoneLevel >= 18:
            keystoneRole = self.helper.getRole(guild, "Legendary")
        if keystoneLevel <= 17:
            keystoneRole = self.helper.getRole(guild, "Epic")
        if keystoneLevel <= 14:
            keystoneRole = self.helper.getRole(guild, "Rare")

        userRoles = data["user"].roles

        if data["additional_roles"]:
            allRoles = ""

            for additionalRole in data["additional_roles"]:
                additionalRole = self.helper.getRoleById(guild, additionalRole["role"])
                allRoles += f"`{additionalRole}`, "
                isAllowedRole = False

                if str(additionalRole) not in self.tankRoles and data["role"] == "Tank":
                    isValid = True
                    isAllowedRole = True
                elif str(additionalRole) not in self.healerRoles and data["role"] == "Healer":
                    isValid = True
                    isAllowedRole = True
                if not isAllowedRole:
                    if additionalRole in userRoles:
                        isValid = True
                        break

            if not isValid:
                await channel.send(f"{data['user'].mention}, you do **NOT** have any of the required {allRoles[:-2]} role(s) to join this group.")
                return False


        if factionRole in userRoles:
            isValid = True
        else:
            await channel.send(f"{data['user'].mention}, you do **NOT** have the required `{factionRole}` role to join this group.")
            return False

        if keystoneRole in userRoles:
            isValid = True
        else:
            await channel.send(f"{data['user'].mention}, you do **NOT** have the required `{keystoneRole}` role to join this group.")
            return False

        if data["role"] != "Any" and data["role"] != "All":
            role = self.helper.getRole(guild, data["role"])
            if role in userRoles:
                isValid = True
            else:
                await channel.send(f"{data['user'].mention}, you do **NOT** have the required `{role}` role to join this group.")
                return False

        if data["armor_type"] != "Any":
            armorRole = self.helper.getRoleById(guild, data["armor_type"])
            isAllowedRole = False

            if str(armorRole) not in self.tankRoles and data["role"] == "Tank":
                isValid = True
                isAllowedRole = True
            elif str(armorRole) not in self.healerRoles and data["role"] == "Healer":
                isValid = True
                isAllowedRole = True
            if not isAllowedRole:
                if armorRole in userRoles:
                    isValid = True
                else:
                    await channel.send(f"{data['user'].mention}, you do **NOT** have the required `{armorRole}` role to join this group.")
                    return False

        if "team" in data:
            teamRole = self.helper.getRole(guild, "M+ TEAM LEADER")
            if teamRole in userRoles:
                isValid = True
            else:
                await channel.send(f"{data['user'].mention}, you do **NOT** have the required `{teamRole}` role to join this group.")
                return False

        return isValid

def setup(client):
    client.add_cog(Generate(client))
