import discord
import re
import subprocess
import aiofiles
import asyncio
import os
import pexpect
import io
import textwrap
import traceback
import functools
from threading import Thread
from queue import Queue, Empty
from datetime import datetime
from shlex import split as shsplit
from os import path
from time import monotonic
from contextlib import redirect_stdout


class Command():
    def __init__(self,aliases=None,coroutine=None,cooldown=False,owner=False,admin=False,name=None):
        self.aliases = aliases or []
        if coroutine is None: raise KeyError('Missing Coroutine')
        self.coroutine = coroutine
        self.cooldown = cooldown
        self.owner = owner
        self.admin = admin
        self.name = name

    def __bool__(self):
        return True

    def __call__(self,**kwargs):
        return self.coroutine(**kwargs)

    def __getitem__(self,key):
        if key == 0: return self.aliases
        if key == 1: return self.coroutine
        if key == 2: return self.cooldown
        if key == 3: return self.owner
        if key == 4: return self.admin

def escape_ansi(line):
    ansi_escape = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', line)

def leftmost_duplicate(s : str) -> int:
    return min(next(ii+len(s[:i+1]) for ii,vv in enumerate(f'{s[i+1:]}') if vv == v) for i,v in enumerate(s) if v in f'{s[i+1:]}')

def unique_num(n):
    try:
        n = abs(int(n))
    except:
        return
    if n > 9876543210: return 9876543210
    ns = f'{n}'
    if len(set(ns)) == len(ns):
        return n
    else:
        i = leftmost_duplicate(ns)

        for ii,vv in reversed(list(enumerate(ns[:i+1]))):
            if ii == 0:
                new_s = f'{int(ns[:ii+1])-1}'
                letters = ''.join(char for char in "9876543210" if not char in new_s)
                return int(f'{new_s}{"".join(letters[:len(ns[ii+1:])])}')
            elif vv != '0' and len([char for char in "9876543210"[-int(vv):] if char not in ns[:ii+1] ]) > 0:
                new_s = f'{ns[:ii]}{next((char for char in "9876543210"[-int(vv):] if char not in ns[:ii+1]))}'
                letters = ''.join(char for char in "9876543210" if not char in new_s)
                return int(f'{new_s}{"".join(letters[:len(ns[ii+1:])])}')


def unique_num_slow(n):
    try:
        n = abs(int(n))
    except:
        return
    if n > 9876543210: n = 9876543210
    while True:
        ns = f'{n}'
        if len(set(ns)) == len(ns):
            return n
        n -= 1


async def num_react(client,message,n):
    old_n = n
    a_num = functools.partial(unique_num, n)
    n = await client.loop.run_in_executor(None, a_num)
    for char in str(n):
        await message.add_reaction(f'{char}\U000020e3')
    if int(old_n) > n: await message.add_reaction('\U00002795')


async def getTemp():
    try:
        with subprocess.Popen(['/opt/vc/bin/vcgencmd', 'measure_temp'], stdout=subprocess.PIPE) as pcputemp:
            while pcputemp.poll() is None:
                await asyncio.sleep(0.05)
            xgputemp = float(re.search("temp=(.*?)'C", str(pcputemp.stdout.read())).group(1))
    except:
        xgputemp = -69

    try:
        fcputemp = await aiofiles.open('/sys/class/thermal/thermal_zone0/temp', 'r')
        xcputemp = float(await fcputemp.read()) / 1000
    except:
        xcputemp = -69

    return xcputemp, xgputemp

async def ignore_modify(client,message,params={},ignore=True):
    users = []
    for ID in params.keys():
        try:
            ID = int(ID)
        except:
            continue
        if client.get_user(ID):
            users.append(ID)
        elif ID in [role.id for role in message.guild.roles]:
            if params.get('unpack'):
                for member in discord.utils.get(message.guild.roles, id=ID).members:
                    users.append(member.id)
            else:
                users.append(ID)
        else:
            try:
                await client.get_user_info(ID)
                users.append(ID)
            except:
                pass
    for user in message.mentions:
        if user != client.user:
            users.append(user.id)
    for role in message.role_mentions:
        if params.get('unpack'):
            for member in role.members:
                users.append(member.id)
        else:
            users.append(role.id)
    if '@everyone' in message.content:
        users.extend([member.id for member in message.guild.members])
    i = len(users)
    if ignore:
        client.ignore_users(users)
    else:
        client.unignore_users(users)
    await num_react(client,message,i)

async def admins_modify(client,message,params={},promote=True):
    users = []
    for ID in params.keys():
        try:
            ID = int(ID)
        except:
            continue
        if ID in [role.id for role in message.guild.roles] or client.get_user(ID) or (await client.get_user_info(ID)):
            users.append(ID)
    for user in message.mentions:
        if user != client.user:
            users.append(user.id)
    for role in message.role_mentions:
        if params.get('unpack'):
            for member in role.members:
                users.append(member.id)
        else:
            users.append(role.id)
    i = len(users)
    if promote:
        client.promote_users(users)
    else:
        client.demote_users(users)
    await num_react(client,message,i)

async def cExec(client,message, params={}):
    '''Executes shit.'''
    stdin = []
    q = Queue()
    async def read_stdin():
        def check(m):
            return m.author == message.author and m.channel == message.channel
        while True:
            msg = await client.wait_for('message',check=check)
            stdin.append(msg.content)
    def read_stdout(pe):
        while not pe.eof():
            q.put(escape_ansi(pe.readline().decode('utf-8')))

    if len(params.get('ctext')) > 0:
        cmd = params['ctext']
    else:
        await message.add_reaction('\U00002753')
        def check(m):
            return m.author == message.author and m.channel == message.channel
        msg = await client.wait_for('message', check=check)
        await message.remove_reaction('\U00002753', client.user)
        cmd = msg.content
    shcmd = shsplit(cmd)
    try:
        pccommand = pexpect.spawn(shcmd[0], shcmd[1:], timeout=None)
        pccommand.setwinsize(16,70)
        pccommand.setecho(True)
        await message.add_reaction('\U00002705')
    except FileNotFoundError:
        await message.add_reaction('\U0000274c')
        return

    stdinTask = client.loop.create_task(read_stdin())

    t = Thread(target=read_stdout, args=(pccommand,))
    t.daemon = True
    t.start()

    embedm = await message.channel.send(content=f'Executing `{cmd}`\n```   ```')
    embedupdate = monotonic()
    pcoutput = ""
    embedlastout = ""
    newline = '\n'
    b = '\U0001f171'
    while pccommand.isalive() or not q.empty():
        try:
            line = q.get_nowait()
        except Empty:
            pass
        else:
            pcoutput = f'{pcoutput}{line}'
        if embedupdate+1.5 < monotonic() and pcoutput != embedlastout:
            embedupdate = monotonic()
            embedlastout = pcoutput
            await embedm.edit(content=f'Executing `{cmd}`\n```{newline.join(pcoutput.splitlines()[-15:])}```')
        for msgin in list(stdin):
            if msgin.startswith(f'{b}kill'):
                pccommand.terminate(force=True)
            elif msgin.startswith(f'{b}close'):
                pccommand.sendintr()
            elif msgin.startswith(f'{b}eof'):
                pccommand.sendeof()
            elif msgin.startswith(f'{b}enter'):
                pccommand.sendline()
            elif msgin.startswith(f'{b}term'):
                pccommand.terminate()
            elif msgin.startswith(f'{b}'):
                pass
            elif msgin.startswith('```'):
                pccommand.sendline(msgin[3:-3])
            elif msgin.startswith('ok i screwed up pls kill it now'):
                pccommand.terminate(force=True)
            else:
                pccommand.sendline(msgin.encode('utf-8'))

            stdin.remove(msgin)

        await asyncio.sleep(0.05)
    stdinTask.cancel()
    pccommand.close()
    if pccommand.exitstatus:
        exitcode = pccommand.exitstatus
    else:
        exitcode = pccommand.signalstatus

    pcoutput = f'{pcoutput}\nReturned with: {exitcode}'
    await embedm.edit(content=f'Executing `{cmd}`\n```{newline.join(pcoutput.splitlines()[-15:])}```')

async def cEval(client,message, params={}):
    '''Evaluates shit.'''
    if len(params.get('ctext')) > 0:
        body = params['ctext']
        msg = message
    else:
        await message.add_reaction('\U00002753')
        def check(m):
            return m.author == message.author and m.channel == message.channel
        msg = await client.wait_for('message', check=check)
        await message.remove_reaction('\U00002753', client.user)
        body = msg.content
    env = {
        'bot': client,
        'client': client,
        'channel': message.channel,
        'author': message.author,
        'guild': message.guild,
        'message': message,
        'message2': msg,
        'params':params
    }

    env.update(globals())

    if body.startswith('```py'):
        body = body[5:-3]
    elif body.startswith('```py'):
        body = body[3:-3]
    elif body.startswith('`'):
        body = body[1:-1]

    stdout = io.StringIO()

    to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

    try:
        exec(to_compile, env)
    except Exception as e:
        return await message.channel.send(f'```py\n{e.__class__.__name__}: {e}\n```')

    func = env['func']
    try:
        with redirect_stdout(stdout):
            ret = await func()
    except Exception as e:
        value = stdout.getvalue()
        await message.channel.send(f'```py\n{value}{traceback.format_exc()}\n```')
    else:
        value = stdout.getvalue()
        try:
            await msg.add_reaction('\u2705')
        except:
            pass

        if ret is None:
            if value:
                await message.channel.send(f'```py\n{value}\n```')
        else:
            await message.channel.send(f'```py\n{value}{ret}\n```')

async def cReload(client,message, params={}):
    '''Reloads the bot. '''
    await message.add_reaction('\U0000267b')
    async with aiofiles.open(path.join(client.dirs['logs'], 'reload'), ('w+')) as reloadfile:
        await reloadfile.write(str(message.channel.id))
    await client.logout()
    client.session.close()
    exit()

async def cShutdown(client,message,params={}):
    '''Turns off the bot hardware.'''
    await message.add_reaction('\U0000267b')
    async with aiofiles.open(path.join(client.dirs['logs'], 'reload'), ('w+')) as reloadfile:
        await reloadfile.write(str(message.channel.id))
    command = "/usr/bin/sudo /sbin/shutdown now"
    subprocess.call(command.split())

async def cPrefix(client, message, params={}):
    '''mate there is no prefix'''
    await message.channel.send('No prefix, simply mention me anywhere in your command.')

async def cHelp(client, message, params={}):
    '''Get help for the bot. admin/all to see admin commands'''
    hCommands = {}
    admin = params.get('admin') or params.get('owner') or params.get('all')
    for key, command in client.commands.items():
        if params.get(key):
            hCommands[key] = command
            next
        for cmdName in command[0]:
            if params.get(cmdName):
                hCommands[key] = command
                break
    if not hCommands:
        if admin:
            hCommands = client.commands
        else:
            hCommands = {key:command for key, command in client.commands.items() if not command[3] }

    embed = discord.Embed()
    embed.title = f'Help for {client.user.display_name}'
    embed.type = 'rich'
    embed.description = 'To use a command mention me with the command name and any parameters.\n' \
                        'Named parameters are called by name=value\n' \
                        '\U0001f550 are \'blocking\' commands'
    embed.colour = discord.Color.gold()
    for key, command in hCommands.items():
        if command[2]:
            aliases = ['\U0001f550 ' + key]
        else:
            aliases = [key]
        aliases.extend(command[0])
        if command[3]:
            embed.add_field(name=f"{'/'.join(aliases)}  **ADMIN ONLY** ", value=command[1].__doc__, inline=False)
        else:
            embed.add_field(name=f"{'/'.join(aliases)}", value=command[1].__doc__, inline=False)

    await message.channel.send(embed=embed)

async def cStatus(client, message, params={}):
    '''Returns misc bot information'''
    #async with client.session.get("http://icanhazip.com/") as IP:
    async with client.session.get("http://ipecho.net/plain/") as IP:
        tIP = str(await IP.text())[:-1]
    pping = subprocess.Popen(['ping', '-c 1', '8.8.8.8'], stdout=subprocess.PIPE)
    while pping.poll() is None:
        await asyncio.sleep(0.05)
    xping = re.search('time=(.*?) ms', str(pping.stdout.read())).group(1)

    xcputemp, xgputemp = await getTemp()
    embed = discord.Embed(title="Status", description=f"Requested by {message.author.mention}",
                          color=discord.Color.green())
    embed.add_field(name='GPU Temperature', value=f'{xgputemp}°C', inline=True)
    embed.add_field(name='CPU Temperature', value=f'{round(xcputemp,1)}°C', inline=True)
    embed.add_field(name='Ping', value=f'{xping}ms', inline=True)
    embed.add_field(name='Local Time', value=datetime.now().strftime('%H:%M:%S UTC+1'), inline=True)
    await message.channel.send(embed=embed)

async def cDebug(client, message, params={}):
    '''Prints the console output'''
    async with aiofiles.open(path.join(client.dirs['logs'], 'stdout.log'), "r") as logfile:
        logs = await logfile.readlines()
        try:
            lines = max(1, min(20, int(params.get('lines') or params.get('l') or params.get('i'))))
        except TypeError as e:
            lines = 10
        await message.channel.send(f"```{''.join(logs[-lines:])}```")

async def cIgnore(client,message,params={}):
    '''Ignores users '''
    await ignore_modify(client,message,params)

async def cUnIgnore(client, message, params={}):
    '''Unignores users '''
    await ignore_modify(client, message, params,ignore=False)

async def cPromote(client, message, params={}):
    '''Promote users to admin '''
    await admins_modify(client, message, params)

async def cDemote(client, message, params={}):
    '''Demote users from admin'''
    await admins_modify(client, message, params,promote=False)


commands = {
    'reload':Command(aliases=['relaod', 'restart'], coroutine=cReload, admin=True),
    'shutdown':Command(aliases=['goodnight'], coroutine=cShutdown, owner=True),
    'status':Command(aliases=['info'], coroutine=cStatus),
    'help':Command(aliases=['commands'], coroutine=cHelp),
    'prefix':Command(coroutine=cPrefix),
    'debug':Command(aliases=['error'], coroutine=cDebug, owner=True),
    'exec':Command(coroutine=cExec, owner=True),
    'ignore':Command(coroutine=cIgnore, admin=True),
    'unignore':Command(coroutine=cUnIgnore, admin=True),
    'promote':Command(coroutine=cPromote, owner=True),
    'demote':Command(coroutine=cDemote, owner= True),
    'eval':Command(aliases=['evaluate'], coroutine=cEval, cooldown=False, owner=True)
}