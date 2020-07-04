import discord
import json

from discord.utils import get
from discord.ext import commands
from gsheet import *

sheet = gsheet()

with open('./config.json', 'r') as cjson:
    config = json.load(cjson)

class Balance(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.command()
    async def balance(self, ctx):
        if isinstance(ctx.message.channel, discord.DMChannel):
            await ctx.message.channel.send("This feature is, sadly, not supported. Type the command in the correct channel and I will DM your balance.")
            return

        embed = discord.Embed(color=0x3090d9, title="Balance Check")
        embed.description = "Please check private messages for balance details."
        await ctx.message.channel.send(embed=embed)

        author = ctx.message.author
        SPREADSHEET_ID = config["SPREADSHEET_ID"]
        allRows = sheet.getAllRows(SPREADSHEET_ID, "'Booster payments'!C13:D")

        for i in range(len(allRows)):
            if allRows[i][0] == author.display_name:
                try:
                    balance = allRows[i][1]
                except:
                    balance = 0

                balanceEmbed = discord.Embed(color=0x3090d9, title="Balance Information")
                balanceEmbed.add_field(name="Current Balance", value=balance)

                await author.send(embed=balanceEmbed)
                return

        await author.send("Your balance could not be retrieved. Please message someone from Council or Management.")

def setup(client):
    client.add_cog(Balance(client))