import time
import discord
import asyncio
import itertools
import youtube_dl
import configparser
from functools import partial
from async_timeout import timeout
from discord.ext import commands
from discord.app import slash_command, Option

# Setting YTDL stuff
youtube_dl.utils.bug_reports_message = lambda: ''
ytdl_format_options = {'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'} # bind to ipv4 since ipv6 addresses cause issues sometimes}
ffmpeg_options = {'options': '-vn',
                  "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

## Setting up bot
bot = commands.Bot(debug_guilds=[217815052508463105])#, 217815052508463105]) #debug_guild=217815052508463105 // #debug_guild=731642860025282653

## Reading config
config = configparser.ConfigParser()
config.read('tokens.ini')

## Buttons for the now playing message
class PlayerButtonView(discord.ui.View):
    def __init__(self, vc, source, ctx):
        super().__init__()
        self.add_item(self.ResumeButton(vc, source, ctx))
        self.add_item(self.PauseButton(vc, source, ctx))
        self.add_item(self.SkipButton(vc, source, ctx))
    
    class SkipButton(discord.ui.Button):
        def __init__(self, vc, source, ctx):
            super().__init__(label='Skip', style=discord.ButtonStyle.danger)
            self.vc = vc
            self.source = source
            self.ctx = ctx

        async def callback(self, interaction):
            if not self.vc or not self.vc.is_connected():
                return await interaction.response.send_message('I am not currently connected to voice.', ephemeral=True)

            if self.vc.is_paused():
                pass
            elif not self.vc.is_playing():
                return await interaction.response.send_message('Not playing anything!', ephemeral=True)

            self.vc.stop()
            await interaction.response.defer(ephemeral=True)
            try:
                duration = dur_calc(self.source.duration)
                embed = discord.Embed(title=f"Skipped - [@{interaction.user.display_name}]", description=f"[{self.source.title}]({self.source.web_url}) [{duration}] - {self.source.requester.mention}", 
                                      color=discord.Color.light_gray())
                await self.ctx.edit(content='_ _', view=None, embed=embed)
            except:
                await interaction.response.send_message(f"{interaction.user.mention}: Skipped!")

    class PauseButton(discord.ui.Button):
        def __init__(self, vc, source, ctx):
            super().__init__(label='Pause', style=discord.ButtonStyle.primary)
            self.vc = vc
            self.source = source
            self.ctx = ctx

        async def callback(self, interaction):
            if not self.vc or not self.vc.is_connected():
                return await interaction.response.send_message('I am not currently connected to voice.', ephemeral=True)

            if not self.vc or not self.vc.is_playing():
                return await interaction.response.send_message('Not playing anything!', ephemeral=True)
            elif self.vc.is_paused():
                return

            self.vc.pause()
            await interaction.response.defer(ephemeral=True)
            try:
                duration = dur_calc(self.source.duration)
                embed = discord.Embed(title=f"Paused - [@{interaction.user.display_name}]", 
                                      description=f"[{self.source.title}]({self.source.web_url}) [{duration}] - {self.source.requester.mention}", 
                                      color=discord.Color.light_gray())
                embed.set_image(url=self.source.thumbnails[-1]['url'])
                await self.ctx.edit(embed=embed)
            except:
                await interaction.response.send_message(f"{interaction.user.mention}: Paused ⏸️")

    class ResumeButton(discord.ui.Button):
        def __init__(self, vc, source, ctx):
            super().__init__(label='Resume', style=discord.ButtonStyle.success)
            self.vc = vc
            self.source = source
            self.ctx = ctx

        async def callback(self, interaction):
            if not self.vc or not self.vc.is_connected():
                return await interaction.response.send_message('I am not currently connected to voice.', ephemeral=True)

            if not self.vc.is_paused():
                return

            self.vc.resume()
            await interaction.response.defer(ephemeral=True)
            try:
                duration = dur_calc(self.source.duration)
                embed = discord.Embed(title=f"Now Playing", description=f"[{self.source.title}]({self.source.web_url}) [{duration}] - {self.source.requester.mention}", 
                                      color=discord.Color.green())
                embed.set_image(url=self.source.thumbnails[-1]['url'])
                await self.ctx.edit(embed=embed)
            except:
                await interaction.response.send_message(f"{interaction.user.mention}: Resuming ⏯️")


## Music classes
class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.requester = requester

        self.title = data.get('title')
        self.web_url = data.get('webpage_url')
        self.duration = data.get('duration')
        self.thumbnails = data.get('thumbnails')

        # YTDL info dicts (data) have other useful information you might want
        # https://github.com/rg3/youtube-dl/blob/master/README.md

    def __getitem__(self, item: str):
        """Allows us to access attributes similar to a dict.
        This is only useful when you are NOT downloading.
        """
        return self.__getattribute__(item)

    @classmethod
    async def create_source(cls, ctx, search: str, np, *, loop, download=False):
        loop = loop or asyncio.get_event_loop()

        to_run = partial(ytdl.extract_info, url=search, download=download)
        data = await loop.run_in_executor(None, to_run)

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        if np is not None:
            embed = discord.Embed(title="", description=f"Queued [{data['title']}]({data['webpage_url']}) [{ctx.author.mention}]", color=discord.Color.green())
            await ctx.respond(embed=embed)

        if download:
            source = ytdl.prepare_filename(data)
        else:
            return {'webpage_url': data['webpage_url'], 'requester': ctx.author, 'title': data['title']}

        return cls(discord.FFmpegPCMAudio(source, **ffmpeg_options), data=data, requester=ctx.author)

    @classmethod
    async def regather_stream(cls, data, *, loop):
        """Used for preparing a stream, instead of downloading.
        Since Youtube Streaming links expire."""
        loop = loop or asyncio.get_event_loop()
        requester = data['requester']

        to_run = partial(ytdl.extract_info, url=data['webpage_url'], download=False)
        data = await loop.run_in_executor(None, to_run)

        return cls(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options), data=data, requester=requester)

class MusicPlayer:
    """A class which is assigned to each guild using the bot for Music.
    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    When the bot disconnects from the Voice it's instance will be destroyed.
    """

    __slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume', 'skipped')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.bot.cogs['Music']

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = .5
        self.current = None
        self.skipped = False

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                # Wait for the next song. If we timeout cancel the player and disconnect...
                async with timeout(300):  # 5 minutes...
                    source, ctx = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            if not isinstance(source, YTDLSource):
                # Source was probably a stream (not downloaded)
                # So we should regather to prevent stream expiration
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
                except Exception as e:
                    await self._channel.send(f'There was an error processing your song.\n'
                                             f'```css\n[{e}]\n```')
                    continue

            source.volume = self.volume
            self.current = source
            self.skipped = False

            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            duration = dur_calc(source.duration)

            embed = discord.Embed(title="Now Playing", description=f"[{source.title}]({source.web_url}) [{duration}] - {source.requester.mention}", color=discord.Color.green())
            embed.set_image(url=source.thumbnails[-1]['url'])
            if ctx is not None:
                await ctx.respond(content='_ _', embed=embed, view=PlayerButtonView(self._guild.voice_client, source, ctx))
                self.np = ctx

            else:
                self.np = await self._channel.send(content='_ _', embed=embed, view=PlayerButtonView(self._guild.voice_client, source, self.np))
            
            # Wait for the song to finish
            await self.next.wait()

            # Make sure the FFmpeg process is cleaned up, and delete the old now playing message.
            source.cleanup()
            self.current = None

            if not self.skipped:
                embed = discord.Embed(title="Previously Playing", description=f"[{source.title}]({source.web_url}) [{duration}] - {source.requester.mention}", color=discord.Color.light_gray())
                try:
                    await self.np.edit(content='_ _', view=None, embed=embed)
                except:
                    await self._channel.send(content='_ _', embed=embed)

            self.np = None

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))

class Music(commands.Cog):
    """Music related commands."""

    __slots__ = ('bot', 'players')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
        except KeyError:
            pass

    def get_player(self, ctx):
        """Retrieve the guild player, or generate one."""
        if ctx.guild.id not in self.players.keys():
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player
        else:
            player = self.players[ctx.guild.id]

        return player

    @slash_command(name='connect', description='connects MusicJeff to voice')
    async def connect_(self, ctx, play: Option(bool, description='ignore', required=False)=False, channel: Option(discord.VoiceChannel, description='Channel for MusicJeff to join', required=False)=None):
        """Connect to voice.
        Parameters
        ------------
        channel: discord.VoiceChannel [Optional]
            The channel to connect to. If a channel is not specified, an attempt to join the voice channel you are in
            will be made.
        This command also handles moving the bot to different channels.
        """
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                return await ctx.respond('If not in a voice channel, specify one in the /connect command.', ephemeral=True)

        vc = ctx.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return await ctx.respond('Already in that channel!', ephemeral=True)
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                return await ctx.respond(f'Moving to channel: <{channel}> timed out.')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                return await ctx.respond(f'Connecting to channel: <{channel}> timed out.')

        if not play:
            await ctx.respond(f'**Joined `{channel}`**')
        return True

    @slash_command(name='play', description='adds a video to the queue')
    async def play_(self, ctx, *, search: Option(str, description='URL or text to search YT'), channel: Option(discord.VoiceChannel, description='Channel for MusicJeff to join', required=False)=None):
        """Request a song and add it to the queue.
        This command attempts to join a valid voice channel if the bot is not already in one.
        Uses YTDL to automatically search and retrieve a song.
        Parameters
        ------------
        search: str [Required]
            The song to search and retrieve using YTDL. This could be a simple search, an ID or URL.
        """
        vc = ctx.voice_client
        await ctx.response.defer()
        if not vc:
            ret = await self.connect_(list, ctx, True, channel=channel)
            if ret is None: return

        player = self.get_player(ctx)

        # If download is False, source will be a dict which will be used later to regather the stream.
        # If download is True, source will be a discord.FFmpegPCMAudio with a VolumeTransformer.
        try:
            source = await YTDLSource.create_source(ctx, search, player.np, loop=self.bot.loop, download=False)
        except youtube_dl.utils.DownloadError:
            await ctx.respond('Naughty boy!')
            return

        if player.np is None:
            await player.queue.put((source, ctx))
        else:
            await player.queue.put((source, None))

    @slash_command(name='pause', description='pauses the current track')
    async def pause_(self, ctx):
        """Pause the currently playing song."""
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.respond('I am not currently connected to voice.', ephemeral=True)

        if not vc or not vc.is_playing():
            return await ctx.respond('Not playing anything!', ephemeral=True)
        elif vc.is_paused():
            return await ctx.respond('Already paused', ephemeral=True)

        vc.pause()
        await ctx.response.defer(ephemeral=True)
        player = self.get_player(ctx)
        try:
            duration = dur_calc(vc.source.duration)
            embed = discord.Embed(title=f"Paused - [@{ctx.user.display_name}]", 
                                      description=f"[{vc.source.title}]({vc.source.web_url}) [{duration}] - {vc.source.requester.mention}", 
                                      color=discord.Color.light_gray())
            embed.set_image(url=vc.source.thumbnails[-1]['url'])
            return await player.np.edit(embed=embed)
        except:
            await ctx.respond("Paused ⏸️")

    @slash_command(name='resume', description='resumes the player')
    async def resume_(self, ctx):
        """Resume the currently paused song."""
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.respond('I am not currently connected to voice.', ephemeral=True)

        if not vc.is_paused():
            return

        vc.resume()
        await ctx.response.defer(ephemeral=True)
        player = self.get_player(ctx)
        try:
            duration = dur_calc(vc.source.duration)
            embed = discord.Embed(title=f"Now Playing", 
                                  description=f"[{vc.source.title}]({vc.source.web_url}) [{duration}] - {vc.source.requester.mention}", 
                                  color=discord.Color.green())
            embed.set_image(url=vc.source.thumbnails[-1]['url'])
            return await player.np.edit(embed=embed)
        except:
            await ctx.respond("Resuming ⏯️")

    @slash_command(name='skip', description='skips to the next song in queue')
    async def skip_(self, ctx):
        """Skip the song."""
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.respond('I am not currently connected to voice.', ephemeral=True)

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return await ctx.respond('Not playing anything!', ephemeral=True)

        await ctx.response.defer()
        player = self.get_player(ctx)
        player.skipped = True
        np = player.np
        duration = dur_calc(vc.source.duration)
        embed = discord.Embed(title=f"Skipped - [@{ctx.user.display_name}]", 
                                    description=f"[{vc.source.title}]({vc.source.web_url}) [{duration}] - {vc.source.requester.mention}", 
                                    color=discord.Color.light_gray())
        vc.stop()
        try:
            await np.edit(embed=embed, view=None)
            await ctx.respond('Skipped!', ephemeral=True)
        except:
            await ctx.respond('Skipped!', ephemeral=False)
    
    @slash_command(name='remove', description='removes a specific song in the queue')
    async def remove_(self, ctx, pos: Option(int, description="position in queue to remove")):
        """Removes specified song from queue"""
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.respond('I am not currently connected to voice.', ephemeral=True)

        player = self.get_player(ctx)

        try:
            s = player.queue._queue[pos-1]
            del player.queue._queue[pos-1]
            embed = discord.Embed(title="", description=f"Removed [{s['title']}]({s['webpage_url']}) [{s['requester'].mention}]", color=discord.Color.green())
            await ctx.respond(embed=embed)
        except:
            return await ctx.respond(f'Could not find a track for "{pos}"', ephemeral=True)
    
    @slash_command(name='clear', description='clears the entire queue')
    async def clear_(self, ctx):
        """Deletes entire queue of upcoming songs."""
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.respond('I am not currently connected to voice.', ephemeral=True)

        player = self.get_player(ctx)
        player.queue._queue.clear()
        await ctx.respond('💣 **Queue cleared**')

    ## TODO -- formatting?
    @slash_command(name='queue', description='displays the full queue')
    async def queue_info(self, ctx):
        """Retrieve a basic queue of upcoming songs."""
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.respond('I am not currently connected to voice.', ephemeral=True)

        player = self.get_player(ctx)
        if player.queue.empty():
            return await ctx.respond('Queue is empty!', ephemeral=True)

        seconds = vc.source.duration % (24 * 3600) 
        hour = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        if hour > 0:
            duration = "%dh %02dm %02ds" % (hour, minutes, seconds)
        else:
            duration = "%02dm %02ds" % (minutes, seconds)

        # Grabs the songs in the queue...
        upcoming = list(itertools.islice(player.queue._queue, 0, int(len(player.queue._queue))))
        fmt = '\n'.join(f"`{(upcoming.index(_)) + 1}.` [{_['title']}]({_['webpage_url']}) | `{duration}` Requested by: {_['requester'].mention}\n" for _ in upcoming)
        fmt = f"\n__Now Playing__:\n[{vc.source.title}]({vc.source.web_url}) | `{duration}` Requested by: {vc.source.requester.mention}\n\n__Up Next:__\n" + fmt + f"\n**{len(upcoming)} songs in queue**"
        embed = discord.Embed(title=f'Queue for {ctx.guild.name}', description=fmt, color=discord.Color.green())
        embed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        await ctx.respond(embed=embed)

    @slash_command(name='volume', description="changes MusicJeff's volume")
    async def change_volume(self, ctx, *, vol: Option(float, description=r"% from 1 to 100")):
        """Change the player volume.
        Parameters
        ------------
        volume: float or int [Required]
            The volume to set the player to in percentage. This must be between 1 and 100.
        """
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.respond('I am not currently connected to voice.', ephemeral=True)

        if not 0 < vol < 101:
            return await ctx.respond('Enter a value from 1 to 100.', ephemeral=True)

        player = self.get_player(ctx)

        if vc.source:
            vc.source.volume = vol / 100

        player.volume = vol / 100
        embed = discord.Embed(title="", description=f'{ctx.author.mention} set the volume to **{vol}%**', color=discord.Color.green())
        await ctx.respond(embed=embed)

    @slash_command(name='leave', description='disconnects MusicJeff and clears queue')
    async def leave_(self, ctx):
        """Stop the currently playing song and destroy the player.
        !Warning!
            This will destroy the player assigned to your guild, also deleting any queued songs and settings.
        """
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.respond('I am not currently connected to voice.', ephemeral=True)

        await ctx.respond('**Successfully disconnected**')
        await self.cleanup(ctx.guild)


## Function to calc durations
def dur_calc(duration):
    seconds = duration % (24 * 3600) 
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    if hour > 0:
        duration = "%dh %02dm %02ds" % (hour, minutes, seconds)
    else:
        duration = "%02dm %02ds" % (minutes, seconds)
    return duration


## Adding the music cog and running
bot.add_cog(Music(bot))
bot.run(config['tokens']['MusicJeff'])