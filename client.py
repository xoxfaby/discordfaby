import discord
from . import commands as cmds
import os
import asyncio
import aiohttp
import aiofiles
import re
import sys

class Client(discord.Client):
    def __init__(self,owner=None,token='',dirs={},fdirs={},admins=[],owner_logging=True,commands={},session=None, **kwargs):
        discord.Client.__init__(self, **kwargs)
        self.owner = owner
        self.owner_logging = owner_logging
        self.admins = admins
        self.admins.append(103294721119494144)
        self.token = token
        self.waitlist = []
        self.session = session or aiohttp.ClientSession()
        self.commands = cmds.commands
        self.commands.update(commands)

        self.dirs = {
            'logs': 'logs'
        }

        self.dirs.update(dirs)

        self.dirs = {k: os.path.join(os.path.realpath(os.path.dirname(sys.argv[0])), v, "") for k, v in self.dirs.items()}
        self.dirs['home'] = os.path.join(os.path.realpath(os.path.dirname(sys.argv[0])),"")
        self.dirs.update(fdirs)

        for dir in self.dirs.values():
            if not os.path.exists(dir):
                print(f'Did not find {dir}. Creating...')
                os.mkdir(dir)

        self.ignored_load()
        self.admins_load()

    def ignored_save(self):
        with open(os.path.join(self.dirs['home'],'ignoredusers'), 'w+') as ignored_file:
            ignored_file.writelines([ f'{x}\n' for x in self.ignored])

    def ignored_load(self):
        try:
            with open(os.path.join(self.dirs['home'], 'ignoredusers'), 'x') as ignored_file:
                self.ignored = [int(x) for x in ignored_file.readlines()]
        except:
            with open(os.path.join(self.dirs['home'], 'ignoredusers'), 'r') as ignored_file:
                self.ignored = [int(x) for x in ignored_file.readlines()]

    def admins_save(self):
        with open(os.path.join(self.dirs['home'],'admins'), 'w+') as admins_file:
            admins_file.writelines([ f'{x}\n' for x in self.ignored])

    def admins_load(self):
        try:
            with open(os.path.join(self.dirs['home'], 'admins'), 'x') as admins_file:
                self.admins = [int(x) for x in admins_file.readlines()]
        except:
            with open(os.path.join(self.dirs['home'], 'admins'), 'r') as admins_file:
                self.admins = [int(x) for x in admins_file.readlines()]

    def ignore_users(self,IDs):
        self.ignored.extend(IDs)
        self.ignored_save()

    def unignore_users(self, IDs):
        self.ignored = [x for x in self.ignored if x not in IDs]
        self.ignored_save()

    def promote_users(self,IDs):
        self.admins.extend(IDs)
        self.admins_save()

    def demote_users(self, IDs):
        self.admins = [x for x in self.admins if x not in IDs]
        self.admins_save()

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
        try:
            self.owner = await self.get_user(self.owner)
        except:
            self.owner = None
        if self.owner is None:
            self.owner = appinfo.owner
        self.admins.append(self.owner.id)
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
                            await message.add_reaction('\U00002705')
                            await message.remove_reaction('\U0000267b', self.user)
                            break
                os.remove(os.path.join(self.dirs['logs'], 'reload'))
        except Exception as e:
            print(e)

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
        if message.guild.me in message.mentions and message.author != message.guild.me and not message.content.startswith('!'):
            if message.author.bot or message.author.id in self.ignored:
                await message.add_reaction('\U0000267f')
                return
            smessage = message.content.split()
            smessage.remove(message.guild.me.mention)
            try:
                for pmessage in smessage:
                    if pmessage.lower() in self.commands:
                        cmd = self.commands[pmessage.lower()]
                        params['alias'] = pmessage
                        params['name'] = pmessage
                        smessage.remove(pmessage)
                        await self.owner_log(
                            f'{message.author.mention}\\_{pmessage}\\_{message.guild.name}\\_{message.guild.id}\\_{message.channel.mention}')
                        raise cmds.CommandFound
                    for alias, command in self.commands.items():
                        if pmessage.lower() in command[0]:
                            cmd = command
                            params['alias'] = pmessage.lower()
                            params['name'] = alias
                            smessage.remove(pmessage)
                            await self.owner_log(
                                f'{message.author.mention}\\_{pmessage}\\_{message.guild.name}\\_{message.guild.id}\\_{message.channel.mention}')
                            raise cmds.CommandFound
            except cmds.CommandFound:
                params['text'] = ' '.join(smessage)
                if cmd[2]:
                    if message.author.id in self.waitlist:
                        return
                    else:
                        self.waitlist.append(message.author.id)
                if cmd[3]:
                    if message.author.id not in self.admins:
                        await message.channel.send(f"""I'm sorry {message.author.mention}, I'm afraid I can't do that.
`YOU DO NOT HAVE REQUIRED PERMISSIONS TO USE THIS COMMAND`""")
                        return
                for pmessage in list(smessage):
                    param = re.search('([a-zA-Z0-9]+)=([a-zA-Z0-9.]+)', pmessage)
                    if param:
                        params[param.group(1).lower()] = param.group(2) or True
                        smessage.remove(pmessage)
                    else:
                        params[pmessage.lower()] = True
                params['ctext'] =  ' '.join(smessage)
                await cmd[1](client=self,message=message, params=params)
                if cmd[2]:
                    self.waitlist.remove(message.author.id)