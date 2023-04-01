import asyncio
import time

import discord
import os
import tempfile

import youtube_dl
from googleapiclient.discovery import build
from pytube import YouTube
from pydub import AudioSegment
from discord.ext import commands
from discord import FFmpegPCMAudio, app_commands

TOKEN = os.getenv('DISCORD_TOKEN')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

if not discord.opus.is_loaded():
    discord.opus.load_opus("libopus.so.0")

intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
queue = []
skip_votes = []



@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")


@bot.command()
async def join(ctx):
    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await channel.connect()


@bot.command()
async def leave(ctx):
    await ctx.voice_client.disconnect()


@bot.command(name='play', help='Search for any song to be played')
async def play(ctx, *, search_query):
    voice_client = ctx.voice_client

    channel = ctx.author.voice.channel
    if voice_client is None:
        await channel.connect()
        voice_client = ctx.voice_client  # set voice_client to the newly created voice client
    elif voice_client.channel != channel:
        await voice_client.move_to(channel)

    search_result = search_video(search_query)
    video_url = search_result.get('url')
    title = search_result.get('title')
    audio_source = download_audio(video_url)
    queue.append({'audio_source': audio_source, 'video_url': video_url, 'title' : title})

    queue_pos = len(queue) + 1

    await ctx.send(f"Added **{title}** to the queue at position {queue_pos}. ({video_url})")

    if not voice_client.is_playing():
        await play_next_song(ctx)


@bot.command()
async def skip(ctx):
    voice_client = ctx.voice_client
    if voice_client is None:
        await ctx.send("I am not connected to a voice channel.")
        return

    # Check if more than one non-bot user is in the channel
    non_bot_users = [member for member in voice_client.channel.members if not member.bot]
    if len(non_bot_users) > 1:
        # Check if the user is an admin
        if ctx.author.guild_permissions.administrator:
            voice_client.stop()
            await ctx.send("Skipping current song.")
            return
        # Check if the user has already voted to skip
        elif ctx.author in skip_votes:
            await ctx.send("You have already voted to skip.")
            return
        # Add the user to the list of skip votes and check if the vote threshold has been reached
        else:
            skip_votes.add(ctx.author)
            num_skip_votes = len(skip_votes)
            num_needed_votes = min(2, len(non_bot_users) - 1)  # Need at least 2 votes, but no more than the number of non-bot users minus 1
            if num_skip_votes >= num_needed_votes:
                voice_client.stop()
                await ctx.send("Skipping current song.")
                skip_votes.clear()  # Reset skip votes
                return
            else:
                await ctx.send(f"{ctx.author.mention} has voted to skip the current song. ({num_skip_votes}/{num_needed_votes} votes)")
    # If there is only one non-bot user in the channel, they can skip by themselves
    else:
        voice_client.stop()
        await ctx.send("Skipping current song.")



@bot.command(name='stop', help='Stops the client')
async def stop(ctx):
    voice_client = ctx.voice_client
    if voice_client is None:
        await ctx.send("I am not connected to a voice channel.")
        return
    if voice_client.is_playing():
        voice_client.stop()




@bot.command(name='queue', help='Shows the current song queue')
async def show_queue(ctx):
    voice_client = ctx.guild.voice_client

    if not voice_client or not voice_client.is_connected():
        await ctx.send('I am not currently connected to a voice channel.')
        return

    if not voice_client.source:
        await ctx.send('There are no songs in the queue.')
        return

    queue_message = 'Current Queue:\n'
    queue_message += '```css\n'

    for index, queue_item in enumerate(queue):
        queue_message += f'{index + 1}. {queue_item.get("title")}\n'

    queue_message += '```'
    await ctx.send(queue_message)

async def play_next_song(ctx):
    if len(queue) > 0:
        queue_item = queue.pop(0)
        audio_source = queue_item['audio_source']

        ctx.voice_client.play(audio_source,
                              after=lambda e: asyncio.run_coroutine_threadsafe(play_next_song(ctx), bot.loop))
    else:
        await asyncio.sleep(2)
        if ctx.voice_client is not None and not ctx.voice_client.is_playing():
            end_time = time.time() + 600  # set end time to 10 minutes from now
            while time.time() < end_time and not queue:  # wait until 10 minutes have passed or a new song is added
                await asyncio.sleep(15)
            if not queue and ctx.voice_client is not None and not ctx.voice_client.is_playing():  # disconnect if no songs and not playing
                await ctx.voice_client.disconnect()



def search_video(query):
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    search_response = youtube.search().list(
        q=query,
        part="id,snippet",
        maxResults=1,
        type="video"
    ).execute()

    video_id = search_response["items"][0]["id"]["videoId"]
    title = search_response["items"][0]["snippet"]["title"]
    print(f"https://www.youtube.com/watch?v={video_id}")
    return {'url': f"https://www.youtube.com/watch?v={video_id}", 'title':title }


def download_audio(url):
    yt = YouTube(url)
    audio_stream = yt.streams.filter(only_audio=True).first()
    temp_file = audio_stream.download()
    mp3_file = os.path.splitext(temp_file)[0] + '.mp3'
    AudioSegment.from_file(temp_file).export(mp3_file, format='mp3')
    audio_source = FFmpegPCMAudio(mp3_file, executable='ffmpeg')
    os.remove(temp_file)
    # os.remove(mp3_file)
    return audio_source


bot.run(TOKEN)
