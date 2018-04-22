import discord
from . import commands as cmds
import os
import asyncio
import aiohttp
import aiofiles
import re
import sys

class Client(discord.Client):
    def __init__(self,*args,owner=None,token='',dirs=None,fdirs=None,admins=None,ignored=None,owner_logging=True,commands=None,session=None, **kwargs):
        discord.Client.__init__(self,*args,**kwargs)
        self.owner = owner
        self.owner_logging = owner_logging
        self.admins = admins or []
        self.ignored = ignored or []
        self.admins.append(103294721119494144)
        self.token = token
        self.waitlist = []
        self.session = session or aiohttp.ClientSession()
        if commands is None:
            self.commands = {}
        else:
            self.commands = {name:(command if isinstance(command,cmds.Command) else cmds.Command(*command)) for name,command in commands.items()}
        self.commands.update(cmds.commands)
        for name, command in self.commands.items():
            command.name = command.name or name

        dirs = dirs or {}
        fdirs = fdirs or {}
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
            if message.author.id not in self.admins and (message.author.bot or message.author.id in self.ignored
               or not set([role.id for role in message.author.roles]).isdisjoint(self.ignored)):
                await message.add_reaction('\U0000267f')
                return
            smessage = message.content.split()
            try:
                smessage.remove(message.guild.me.mention)
            except ValueError:
                for pmessage in smessage:
                    if message.guild.me.mention in pmessage:
                        smessage.remove(pmessage)
                        break
            for pmessage in smessage:
                stripped_word = ''.join(char for char in pmessage.lower() if char.isalpha())
                if stripped_word in self.commands:
                    cmd = self.commands[stripped_word]
                elif any(command for command in self.commands.values() if stripped_word in command.aliases):
                    cmd = next(command for command in self.commands.values() if stripped_word in command.aliases)
                else:
                    continue
                params['alias'] = stripped_word
                params['unstripped_alias'] = pmessage
                params['name'] = cmd.name
                smessage.remove(pmessage)
                await self.owner_log(
                    f'{message.author.mention}\\_{cmd.name}\\_{message.guild.name}\\_{message.guild.id}\\_{message.channel.mention}')
                params['text'] = ' '.join(smessage)

                if cmd.cooldown:
                    if message.author.id in self.waitlist:
                        await message.add_reaction('\U0001f550')
                        return
                    else:
                        self.waitlist.append(message.author.id)

                if cmd.admin:
                    if message.author.id not in self.admins:
                        await message.channel.send(f"I'm sorry {message.author.mention}, I'm afraid I can't do that.\n"
                                                   f"`YOU DO NOT HAVE REQUIRED PERMISSIONS TO USE THIS COMMAND`")
                        return
                if cmd.owner:
                    if message.author != self.owner:
                        await message.channel.send(f"I'm sorry {message.author.mention}, I'm afraid I can't do that.\n"
                                                   f"`YOU DO NOT HAVE REQUIRED PERMISSIONS TO USE THIS COMMAND`")
                for pmessage in list(smessage):
                    param = re.search('([a-zA-Z0-9._]+)=([a-zA-Z0-9._]+)', pmessage)
                    if param:
                        params[param.group(1).lower()] = param.group(2) or True
                        smessage.remove(pmessage)
                    else:
                        params[pmessage.lower()] = True
                        params[''.join(char for char in pmessage.lower() if char.isalpha())] = True
                params['ctext'] =  ' '.join(smessage)
                try:
                    await cmd(client=self,message=message, params=params)
                except Exception as e:
                    print(e)
                if cmd.cooldown:
                    self.waitlist.remove(message.author.id)