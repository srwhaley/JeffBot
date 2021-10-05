import re
import time
import configparser
import random
import discord
import asyncio
import requests
import traceback
import numpy as np
from discord import FFmpegPCMAudio, PCMVolumeTransformer


## loading default emotes
config = configparser.ConfigParser()
config.read('emotes.ini')
config.read('tokens.ini')

## client class
class MyClient(discord.Client):
    def __init__(self, q):
        self.timedict = {}
        self.vc = None
        self.queue = q
        super().__init__()
        # self.queue = queue
        # for guild in self.guilds:
        #     self.queue[guild] = []
    
    async def on_message(self, message):
        c_message = message
        c_author = message.author
        c_channel = message.channel
        c_guild = message.guild
        c_text = message.content.lower().strip()
        if c_author.id in self.timedict.keys():
            if time.time() - self.timedict[c_author.id] < 0.5:
                return
            else:
                self.timedict[c_author.id] = time.time()  
        else:
            self.timedict[c_author.id] = time.time()
        
        if c_author.id != self.user.id:
            if c_author.id == 151867104646266880 and np.random.random(1)[0] < 0.5:
                try:
                    emoji = random.choice(c_message.guild.emojis)
                    #emoji = [i for i in c_message.guild.emojis if i.name == 'Pepe_Retarded'][0]
                    await c_message.add_reaction(emoji)
                except:
                    await c_message.add_reaction('💩')
            
            # run through options that don't involve mp3 first
            options = [(c_text[:6] == '.emote' or c_text[:3] == '.e ' or c_text[:4] == '.ffz' or c_text[:5] == '.bttv', emote, (c_message, c_channel, c_text)),
                       (c_text[:5] == '.adde', add_emote, (c_channel, c_text)),
                       (c_text[:7] == '.cached', cached_emotes, (c_channel,)),
                       (re.match(r'.clea[nr] [0-9]+', c_text), cleaner, (c_channel, c_text)),
                       (c_text == '.howdy', howdy, (c_channel,)),
                       (c_text == '.help', helper, (c_channel,)),
                       (c_text == '.f', bigf, (c_channel,)),
                       ('widepeepohappy' in c_text, widepeepo, (c_message, c_channel)),
                       (c_text[:5] == '.flip', coin_flip, (c_channel, c_text)),
                       (c_text[:12] == 'join my coop', bloons, (c_message, c_channel, c_text)),
                       (c_text[:6] == '.annoy', caller, (c_channel, c_message))]
            
            for condition, func, inputs in options:
                if condition:
                    await func(*inputs)
                    return
            
            # then check for mp3
            options = [(c_text == '.jeff', 'jeff'),
                       (c_text == '.ourtown' or c_text == '.yeahbeatit' or c_text == '.scrub', 'ourtown'),
                       (c_text == '.allo', 'allo'),
                       (c_text == '.ussr', 'ussr'),
                       (c_text == '.ussr long', 'ussr long'),
                       (c_text == '.mk' or c_text == '.mustard' or c_text == '.ketchup', 'mustard'),
                       (c_text == '.mayo' or c_text == '.harold', 'mayo'),
                       (c_text == '.hood', 'hood'),
                       (c_text == '.thanks', 'thanks'),
                       (c_text == '.johnson', 'johnson'),
                       (c_text == '.retard' or c_text == '.fire', 'fire')]
            
            for condition, file in options:
                if condition and c_author.voice is not None:
                    # self.queue[c_guild].append((c_author.voice, c_channel, file))
                    self.queue.put_nowait(create_audio_source(c_author, c_channel, file))
                    return

            # if the text is skip, skip currently performing item in queue
            if c_text == '.skip':
                if self.voice_clients:
                    await self.voice_clients[0].disconnect()
                    self.queue.task_done()
            
            elif c_text == '.skip all':
                # otherwise skip everthing in queue
                if self.queue.qsize():
                    for _ in range(self.queue.qsize()):
                        self.queue.get_nowait()
                        self.queue.task_done()
                if self.voice_clients:
                    await self.voice_clients[0].disconnect()


## text commands
async def cleaner(c_channel, c_text):
    num = int(c_text[7:]) + 2
    num = num if num >= 3 else 3
    num = num if num <= 52 else 52
    await c_channel.send(f'Cleaning {num-2} messages...')
    counter = 0
    async for message in c_channel.history(limit=num):
        if counter > 0:
            await message.delete()
        counter += 1
    async for message in c_channel.history(limit=1):
        await message.delete()

async def howdy(c_channel):
    text = ['`\n'+\
            '　　 　　 　 　　:cowboy:\n'+\
            '　　 　　 　　:100::100::100:\n'+\
            '　　  　　　:100: 　:100:　:100:\n'+\
            '　　　  　　:point_down_tone3:   :100::100:　:point_down_tone3:\n'+\
            '　　  　　   　　:100:　 :100:\n'+\
            '　　　　    　　:100:　　:100:\n'+\
            '　　 　 　  　　 :boot:　　:boot:\n']
    for mess in text:
        await c_channel.send(mess)

async def bigf(c_channel):
    a = '`\nFFFFFFFFFFFFFFFFFFF\nFFFFFFFFFFFFFFFFFFF\nFFFFFFFFFFFFFFFFFFF\n'+\
    'FFFFFF\nFFFFFF\nFFFFFF\nFFFFFFFFFFFF\nFFFFFFFFFFFF\nFFFFFFFFFFFF\n'+\
    'FFFFFF\nFFFFFF\nFFFFFF\nFFFFFF\nFFFFFF'
    await c_channel.send(a)

async def helper(c_channel):
    await c_channel.send('Available commands:\n.help\n.jeff\n.clea(n/r) #\n' +\
                         '.ourtown(.yeahbeatit/.scrub)\n.allo\n.howdy\n.F\n' +\
                         '.ussr (long)\n.mustard(.mk/.ketchup)\n.mayo\n.hood\n' +\
                         '.thanks\n.johnson\n.retard\n.e(.emote/.ffz)\n.bttv\n' +\
                         '.cached\n.adde\n.flip (games)\n')

async def widepeepo(c_message, c_channel):
    peepo = 'pics/widepeepohappy.png'
    await c_message.delete()
    await c_channel.send('', file=discord.File(peepo))

async def coin_flip(c_channel, c_text):
    # getting flip format aka game names and bounds to use
    if c_text == '.flip':
        games = ['heads','tails']
        bounds = [0, .5, 1]
    else:
        games = c_text.split(' ')[1:]
        numg = len(games)
        bounds = np.linspace(0,1,numg+1)

    flip = np.random.random(1)[0]
    for i in range(len(bounds)-1):
        if flip >= bounds[i] and flip < bounds[i+1]:
            await c_channel.send(games[i])
            if games[i] == 'heads':
                await c_channel.send(config['emotes']['omegalaughing'])
            elif games[i] == 'tails':
                await c_channel.send(config['emotes']['bussers'])
            break

async def bloons(c_message, c_channel, c_text):
    await c_channel.send(c_text[-6:])
    await c_message.delete()

async def caller(c_channel, c_message):
    await c_channel.send('any <@&282357430531129344> in chat?')
    await c_message.delete()


## bttv/ffz emote commands
async def emote(c_message, c_channel, c_text):
    # setting base urls
    bttv_url = 'https://api.betterttv.net/3/emotes/shared/search?query=$QUERY&offset=0&limit=1'
    cdn_url = 'https://cdn.betterttv.net/emote/'
    ffz_url = 'https://api.frankerfacez.com/v1/emoticons?q=$QUERY&sort=count-desc&days=0'

    # getting user query
    query = c_message.content.split(' ')[-1]

    # if we already have that emote saved, and it wasn't being searched for specifically, just post it
    if query.lower() in config['emotes'].keys() and not (c_text[:4] == '.ffz' or c_text[:5] == '.bttv'):
        
        # sending channel message
        await c_channel.send(config['emotes'][query.lower()])
        return

    else: #performing a search
        tried = False
        if c_text[:6] == '.emote' or c_text[:3] == '.e ' or c_text[:4] == '.ffz':
            if re.match(r'[0-9]+', query): # direct id of emote
                res = requests.get(ffz_url.split('emoticons')[0] + 'emote/' + query).json()['emote']
            else: # perform actual search
                res = requests.get(ffz_url.replace('$QUERY', query)).json()['emoticons'][0]

            # sending channel message
            try:
                key = list(res['urls'].keys())[-1]
            except:
                tried = True
            else:
                await c_channel.send('https:'+ res['urls'][key])
                return

        try:
            if c_text[:5] == '.bttv' or tried: # performing search on bttv
                if len(query) == 24: # direct id of emote
                    res = requests.get(bttv_url.split('shared')[0] + query.lower()).json()
                else: #perform actual search
                    res = requests.get(bttv_url.replace('$QUERY', query)).json()[0]
                emote_id = res['id']
                emote_type = res['imageType']

                # getting emote type suffix
                if emote_type == 'gif':
                    cdn_suffix = '/2x.gif'
                else:
                    cdn_suffix = '/2x'

                # sending channel message
                await c_channel.send(cdn_url + emote_id + cdn_suffix)
                return
        except:
            pass

async def add_emote(c_channel, c_text):
    # checking that the message fits the format
    if re.match(r'.adde [a-zA-Z0-9]+ [a-zA-Z0-9./:=$]+', c_text):
        # getting the name and link of emote
        name = c_text.split(' ')[1]
        link = c_text.split(' ')[2]

        # saving the emote
        config['emotes'][name] = link
        with open('emotes.ini','w') as f:
            config.write(f)
        await c_channel.send(f'Successfully added {name}')
    
    else:
        await c_channel.send("Bad format dummy (.adde [emote_name] [link_to_image])")

async def cached_emotes(c_channel):
    es = list(config['emotes'].keys())
    es.sort()
    await c_channel.send('Cached emotes: ' + ', '.join(es))


## audio commands
async def create_audio_source(c_author, c_channel, file):
    uservoice = c_author.voice
    vc = None
    
    # only play music if user is in a voice channel
    if uservoice is not None:
        # get user's voice channel and connect
        voice_channel = uservoice.channel
        vc = await voice_channel.connect()
        # creating the audio source
        audio_source = FFmpegPCMAudio('mp3s/' + file + '.mp3')
        audio_source = PCMVolumeTransformer(audio_source)
        audio_source.volume = 50

        # play audio
        vc.play(audio_source)

    # doing the message sending if needed
    if file == 'ourtown':
        await c_channel.send('(ง ͠° ͟ʖ ͡°)ง ᴛʜɪs ɪs ᴏᴜʀ ᴛᴏwɴ sᴄʀᴜʙ (ง ͠° ͟ʖ ͡°)ง (ง •̀•́)ง *ʏᴇᴀʜ ʙᴇᴀᴛ ɪᴛ!* (ง •̀•́)ง')
    elif file == 'jeff':
        jefffile = 'pics/jeff.png'
        message = await c_channel.send('my name jeff', file=discord.File(jefffile))
        await message.add_reaction('🤠')
        await message.add_reaction('👉')
        await message.add_reaction('👌')
        await message.add_reaction('❓')
    elif file == 'johnson':
        johnfile = 'pics/johnson.gif'
        message = await c_channel.send('', file=discord.File(johnfile))

    # disconnecting the audio from channel
    if vc is not None:
        while True:
            if vc.is_playing():
                await asyncio.sleep(0.5)
            else:
                await vc.disconnect()
                break


## the queue
async def myqueue(q):
    # constantly get the next item out of queue
    while True:
        # will wait until next item is in queue
        a = await q.get()
        # await the item until it is complete
        try:
            await a
        except:
            traceback.print_exc()
        # call a sleep (helps with timings)
        await asyncio.sleep(0.25)

        # try to call the item done. it's in a try because of the skip commands
        try:
            q.task_done()
        except:
            pass

if __name__ == '__main__':
    q = asyncio.Queue()
    asyncio.Task(myqueue(q))
    client = MyClient(q)
    client.run(config['tokens']['JeffBot'])