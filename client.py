import discord
from . import commands as cmds
import os
import asyncio
import aiohttp
import aiofiles
import re

class Client(discord.Client):
    def __init__(self,owner=None,token='',dirs={},owner_logging=True,commands={},session=None, **kwargs):
        discord.Client.__init__(self, **kwargs)
        self.owner = owner
        self.owner_logging = owner_logging
        self.token = token
        self.waitlist = []
        self.session = session or aiohttp.ClientSession()
        self.commands = cmds.commands
        self.commands.update(commands)

        self.dirs = {
            'logs': 'logs'
        }

        self.dirs.update(dirs)

        self.dirs = {k: os.path.join(os.getcwd(), v) for k, v in self.dirs.items()}
        self.dirs['home'] = os.getcwd()

        for k, dir in self.dirs.items():
            if not os.path.exists(dir):
                print(f'Did not find {dir}. Creating...')
                os.mkdir(dir)

    async def owner_log(self,message):
        if self.owner_logging:
            while not self.is_ready():
                asyncio.sleep(0.1)
            await self.owner.send(message)

    async def on_message(self,message):
        await self.parse_commands(message)

    async def on_ready(self):
        await self.process_ready()


    async def process_ready(self):
        appinfo = await self.application_info()
        if self.owner is None:
            self.owner = appinfo.owner
        else:
            self.owner = await self.get_user(self.owner)
        self.owner = appinfo.owner
        for privatechannel in self.private_channels:
            async for message in privatechannel.history(limit=100):
                if discord.utils.get(message.reactions, me=True) is None and message.author != self.user:
                    await self.owner_log(message.author.mention + " " + message.content)
                    await message.add_reaction('\U00002705')

        try:
            if os.path.isfile(os.path.join(self.dirs['logs'], 'reload')):
                async with aiofiles.open(os.path.join(self.dirs['logs'], 'reload'), ('r')) as reloadfile:
                    async for message in self.get_channel(int(await reloadfile.read())).history(limit=20):
                        if discord.utils.get(message.reactions, emoji='\U0000267b', me=True):
                            await message.remove_reaction('\U0000267b', self.user)
                            await message.add_reaction('\U00002705')
                            break
                os.remove(os.path.join(self.dirs['logs'], 'reload'))
        except Exception as e:
            print(e)
            pass

        async with self.session.get("http://icanhazip.com/") as IP:
            IPtext = await IP.text()
            await self.owner_log(f"{appinfo.name} running on {IPtext}")







    async def parse_commands(self,message):
        if isinstance(message.channel, discord.abc.PrivateChannel):
            if message.author != message.channel.me:
                await self.owner_log(f'{message.author.mention}:{message.content}')
                await message.add_reaction('\U00002705')
                await message.channel.send("Sorry, no private commands at the moment.")
            return
        cmd = None
        params = {}
        if message.guild.me in message.mentions and message.author != message.guild.me:
            smessage = message.content.split()
            try:
                for pmessage in smessage:
                    if pmessage.lower() in self.commands:
                        cmd = self.commands[pmessage.lower()]
                        smessage.remove(pmessage)
                        await self.owner_log(
                            f'{message.author.mention}\\_{pmessage}\\_{message.guild.name}\\_{message.guild.id}\\_{message.channel.mention}')
                        raise cmds.CommandFound
                for pmessage in smessage:
                    for alias, command in self.commands.items():
                        if pmessage.lower() in command[0]:
                            if command[2]:
                                if message.author.id in self.waitlist:
                                    return
                                else:
                                    self.waitlist.append(message.author.id)

                            cmd = command
                            smessage.remove(pmessage)
                            await self.owner_log(
                                f'{message.author.mention}\\_{pmessage}\\_{message.guild.name}\\_{message.guild.id}\\_{message.channel.mention}')
                            raise cmds.CommandFound
            except cmds.CommandFound:
                for pmessage in smessage:
                    param = re.search('([a-zA-Z0-9]+)=([a-zA-Z0-9\.]+)', pmessage)
                    if param:
                        params[param.group(1).lower()] = param.group(2) or True
                    else:
                        params[pmessage.lower()] = True

                await cmd[1](client=self,message=message, params=params)
                if cmd[2]:
                    self.waitlist.remove(message.author.id)