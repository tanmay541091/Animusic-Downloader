
from __future__ import unicode_literals
from xml.etree import ElementTree as Xet
import csv
import pandas as pd
import urllib3
import requests
#pip install requests beautifulsoup4 
import bs4
from bs4 import BeautifulSoup as bs

#https://github.com/LaurenceRawlings/savify
#pip install -U savify
from savify import Savify
from savify.types import Type, Format, Quality
from savify.utils import PathHolder
from savify.logger import Logger

#https://github.com/alexmercerind/youtube-search-python
#pip install youtube-search-python
import youtubesearchpython as yts

#https://github.com/ytdl-org/youtube-dl#embedding-youtube-dl
#https://stackoverflow.com/questions/32482230/how-to-set-up-default-download-location-in-youtube-dl
import youtube_dl
import os

#unused
#pip install music-tag
#%pip install pytube
#from pytube import YouTube



#Module 1: Playing with html pages
#converts the xml page into a dataframe, filters based on watching/completed and also adds mal link in last column
def MakeCSV(exportedxml):
    xml = Xet.parse(exportedxml)
    csvfile = open('mal_to_csv.csv','w',encoding='utf-8')
    csvfile_writer = csv.writer(csvfile)
    csvfile_writer.writerow(['AnimeTitle','ID','Status'])

    for anime in xml.findall('anime'):
        if(anime):
            animename = anime.find('series_title')
            animeid = anime.find('series_animedb_id')
            animestatus = anime.find('my_status')
            csv_line = [animename.text, animeid.text, animestatus.text]
            csvfile_writer.writerow(csv_line)
    csvfile.close()  

    df = pd.read_csv('mal_to_csv.csv')
    df2= df.dropna()
    filters = ['Completed', 'Watching']
    df3 = df2[df2['Status'].isin(['Completed', 'Watching'])].reset_index()
    del df3['index']
    def make_url(row):
        return 'https://myanimelist.net/anime/' + str(row[1])
    df3['URL'] = df3.apply(make_url, axis = 1)
    return df3

#this function gives the title, season and year of the anime as a list
def AnimeAndSeason(entry_page):
    #title  = entry_page.title.text.replace('\n', ' ').strip(' MyAnimeList.net')
    #title  = title.strip(' -')
    title  = entry_page.title.text.replace('\n', ' ').split(' - ')[0].strip()
    links  = entry_page.select('span > a')
    years  = range(1900,2050)
    season = ''
    year   = 1900
    for row in links:
        test = row.contents[0].split()
        if len(test) == 2 and test[1].isdigit() and int(test[1]) in years:
            season_info = test
            season = season_info[0] + ' ' + season_info[1]
            year = int(season_info[1])
    return(title, season, year)

#function below gives a lil bit fucked list of the category/song/artist for individual mal page
def SongAndArtist(entry_page):
    testing = entry_page.find_all('div', attrs={'class':'di-tc va-t'})
    testing2 = entry_page.find_all('div', attrs={'class':'di-tc va-t borderDark pb4'})
    testing3 = testing + testing2
    SAAlist = []
    for entry in testing3:
        category = entry.h2
        if type(category) == bs4.element.Tag: 
            category_name = category.contents
            SAAlist.append(category_name)

        song_td_set = entry.find_all('td', {'width':'84%'})
        for song_td in song_td_set:
            song_data = song_td.text.replace('\n', ' ').strip()
            row = song_data.split('\xa0') #split song# and song-artist
            for datas in row:
                if ' by ' in datas:
                    row2 = datas.split(' by ') #split song and artist
                    data_entry = [row2[0].strip('\"'), row2[1]]  #join song, artist
                    song_links = song_td.find_all('input')
                    for link in song_links:
                        somelink = link['value']
                        if 'spotify' in somelink:
                            data_entry.append(somelink)
                    SAAlist.append(data_entry)
    return SAAlist

#this combines the previous 2 functions and gives a nice dataframe of each row having all the identifying factors of a song
def CreateSongDF(entry_page):
    aas = AnimeAndSeason(entry_page)
    saa = SongAndArtist(entry_page)
    if aas[0] == 'Gyo (GYO: Tokyo Fish Attack!)': saa[2][0] = 'End Theme'
        
    for line in saa:
        if 'Opening Theme' in line: op_index = saa.index(line)
        if 'Ending Theme' in line: ed_index = saa.index(line)
            
    OP = []
    category = saa[op_index][0]
    for op in range(op_index+1,ed_index):
        temp = saa[op]
        temp.insert(0,category)
        OP.append(temp)

    ED = []
    category = saa[ed_index][0]
    for ed in range(ed_index+1,len(saa)):
        temp = saa[ed]
        temp.insert(0,category)
        ED.append(temp)
    
    def Clean_Blanks(List, Length):
        for item in List:
            if len(item) != Length:
                item.extend(' ')
       
    Clean_Blanks(ED, 4)
    Clean_Blanks(OP, 4)
    song_columns = ['category', 'songname', 'artist', 'link']
    opdb = pd.DataFrame(OP, columns = song_columns)
    eddb = pd.DataFrame(ED, columns = song_columns)
    SongDB = pd.concat([opdb,eddb], axis = 0, ignore_index = True)
    SongDB['extra'] = ''
    return SongDB

#Module 2: Playing with internet for spotify and youtube links
#this creates a new dataframe (withc columns as song metadata and a 'links' column) from the csv containing mal urls
def GetSpotify(malcsv):
    song_table = pd.read_csv(malcsv).reset_index()
    song_table.drop(['Unnamed: 0', 'index'], inplace=True, axis=1)    
    link_table = pd.DataFrame(columns = ['anime', 'season', 'year','category', 'songname', 'artist', 'link', 'extra'])
    for i in song_table.index:
        anime_link = song_table.loc[i,'URL']
        html       = requests.get(anime_link).text #type: ignore       
        mal_page   = bs(html, 'lxml')  
        aas        = AnimeAndSeason(mal_page)

        song_subtable    = CreateSongDF(mal_page)
        anime_subtable   = pd.DataFrame(columns=['anime', 'season', 'year'])
        print('Fetching spotify links for', aas[0])
        
        for i in range(0, len(song_subtable)):
            anime_subtable.loc[i,'anime']  = aas[0]
            anime_subtable.loc[i,'season'] = aas[1]
            anime_subtable.loc[i,'year']   = aas[2]
        anime_subtable = pd.concat([anime_subtable, song_subtable], axis = 1)
        link_table     = pd.concat([link_table, anime_subtable], axis = 0)
    link_table = link_table.reset_index()
    del link_table['index']
    return link_table

#update the spotify sheet with youtube links as well to get a final sheet with all links
def GetYoutube(spotcsv):
    links.to_csv(spotcsv)
    del link_table['Unnamed: 0']
    for j in link_table.index:
        if 'spotify' in str(link_table.loc[j,'link']) or 'youtube' in str(link_table.loc[j,'link']): continue 

        print(j,'Fetching youtube links for', link_table.loc[j,'anime'],link_table.loc[j,'songname'])
        search_text = link_table.loc[j,'songname'] + ' ' + link_table.loc[j,'artist']
        
        if link_table.loc[j,'extra'] == 'fuckup': search_text = link_table.loc[j,'anime'] + ' ' + link_table.loc[j,'songname']
        if link_table.loc[j,'extra'] == 'fuckup2': search_text = link_table.loc[j,'songname']

        first_result = yts.VideosSearch(search_text, limit = 1).result()
        if first_result['result'] == []: 
            if link_table.loc[j,'extra'] == 'fuckup': link_table.loc[j,'extra'] = 'fuckup2'
            link_table.loc[j,'extra'] = 'fuckup'
            print('youtube search fuckup #')
            continue
            link_table.loc[j,'link'] =  first_result['result'][0]['link']
            link_table.loc[j,'extra'] =  first_result['result'][0]['title']
    link_table['status'] = ''
    return link_table

#function to make all entries in the databases valid filenames
def ValidFile(txt):
    filename = ''
    if '...' in txt:
        txt = txt.strip('...')
    for i in txt:
        if i not in '\/*?<>|"':
            filename = filename + i
        elif i in ':':
            filename = filename + '-'
        else:
            filename = filename + '_'
    return filename

#function to get a different 
def New_Entries(new, old):
    temp = pd.DataFrame(columns = old.columns.tolist())
    for i in new.index:
        link = new.loc[i, 'link']
        song = new.loc[i, 'songname']
        artist = new.loc[i, 'artist']   
        for j in old.index:
            if old.loc[j, 'link'] ==  link:
                link = "BUSTED"
                break
            if 'spotify' not in link and old.loc[j, 'songname'] == song and old.loc[j, 'artist'] == artist: 
                new.loc[i,'extra'] = 'yt upgrade to spot'
    
        if link != "BUSTED": 
            print("found a new link:", link)
            temp = temp.append(new.loc[i], ignore_index = True)
    return temp

#Module 3: Playing with external libraries to download songs
#downloads spotify links into nested folder properly
def DownloadSpotify(sheet_with_spotify, dl_loc, start, end):
    songset = sheet_with_spotify.iloc[start:end]
    for i in songset.index:
        if 'spotify' not in songset.loc[i,'link'] or songset.loc[i,'status'] == 'Downloaded': continue
        #https://developer.spotify.com/dashboard/applications/f2d89a80d48e41e19e4263d5b3792c21 for api credentials
        sp_link = songset.loc[i,'link']
        year    = str(songset.loc[i,'year'])
        season  = str(songset.loc[i,'season'])
        oped    = songset.loc[i,'category']
        anime   = ValidFile(songset.loc[i,'anime'])
        title   = ValidFile(songset.loc[i,'songname'].strip())
        artist  = ValidFile(songset.loc[i,'artist'].strip())
        path    = year + '/' + season + '/' + anime + '/' + oped + '/' + artist + '/'+ title
        ffpath  = 'ffmpeg'
        dlpath  = dl_loc +'/' + 'Animusic'
        api1    = 'f2d89a80d48e41e19e4263d5b3792c21'
        api2    = '12f6688e93504599b3d0403e8a4f2cc8'
        logger  = Logger(log_location = dlpath, log_level = None)
        print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
        print(i, path)
        print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
        
        #C:\Users\dell\AppData\Roaming\Savify\temp is where the temporary download goes
        s = Savify(api_credentials  = (api1,api2), 
                    download_format = Format.MP3, 
                    ffmpeg_location = ffpath, 
                    skip_cover_art  = False, 
                    path_holder = PathHolder(downloads_path=dlpath), 
                    group   = path, 
                    quality = Quality.BEST,
                    logger  = logger)
        s.download(sp_link)
        sheet_with_spotify.loc[i,'status'] = 'Downloaded'

#downloads youtube video bocchi_eyebrow_raise
def DownloadYoutube(sheet_with_youtube, dl_loc, start, end):
    songset2 = sheet_with_youtube.loc[start:end,:]
    for i in songset2.index:
        if 'youtube' not in songset2.loc[i,'link'] or str(songset2.loc[i,'status']) == 'Downloaded' or str(songset2.loc[i,'status']) == 'sus': continue
        year    = str(songset2.loc[i,'year'])
        season  = str(songset2.loc[i,'season'])
        anime   = songset2.loc[i,'anime']
        oped    = songset2.loc[i,'category']
        title   = songset2.loc[i,'songname']
        artist  = songset2.loc[i,'artist']
        yt_link = songset2.loc[i,'link']
        path    = dl_loc + '/' + year + '/' + season + '/' + anime + '/' + oped + '/' + artist + '/'+ title + '/'
        def my_hook(d):
            if d['status'] == 'finished':
                print('~~~~~~', i, title, artist,'~~~~~~')

        ydl_opts = {
            'format': 'bestaudio',
            'outtmpl': path + '%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',}],
                'progress_hooks': [my_hook]}

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([yt_link])
        sheet_with_youtube.loc[i,'status'] = 'Downloaded'
    return sheet_with_youtube
