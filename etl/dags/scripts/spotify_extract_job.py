import pandas as pd
import numpy as np

import json
import logging

from pathlib import Path
import os
import requests
from bs4 import BeautifulSoup
import re

from spotify.lyrics_queries import lyrics
from spotify.api import credentials
from utils.logger import logger
from spotify.get_token import token_web
from airflow.models import Variable

# load_dotenv()
# env_path = Path(".") / ".env"
# load_dotenv(dotenv_path=env_path)

#CLIENT_ID = Variable.get("CLIENT_ID")
#CLIENT_SECRET = Variable.get("CLIENT_SECRET")
#LIMIT = Variable.get("spotify_req_limit")


def spotify_etl_func():

    # sp = credentials(CLIENT_ID, CLIENT_SECRET, LIMIT)

    # data = sp.current_user_recently_played(
    #     limit=LIMIT
    # )  


    # Hot fix for docker - web browser token Spotify
    data = token_web(LIMIT=10)

    logger.info("Connected to Spotify...")

    if data is None:
        logger.info("No songs downloaded. Finishing execution")
        return False

    logger.info("Writing raw JSON file...")
    with open("data/dump.json", "w") as f:
        json.dump(data, f)

    song_list = []
    lyrics_list = []

    for song in data["items"]:
        song_id = song["track"]["id"]
        song_name = song["track"]["name"]
        song_img = song["track"]["album"]["images"][0]["url"]
        song_url = song["track"]["external_urls"]["spotify"]
        song_duration = song["track"]["duration_ms"]
        song_explicit = song["track"]["explicit"]
        song_popularity = song["track"]["popularity"]
        date_time_played = song["played_at"]
        album_id = song["track"]["album"]["id"]
        artist_id = song["track"]["album"]["artists"][0]["name"]

        # Release Year
        try:
            r = requests.get(
                "https://musicbrainz.org/search?query={}+{}&type=release&method=indexed".format(
                    artist_id, song_name
                ).replace(
                    " ", "+"
                )
            )
            soup = BeautifulSoup(r.content, "lxml")
            yearHTML = soup.find_all("span", "release-date")[0]  # Select first result

            year = re.findall(r"[0-9]+", str(yearHTML))

            scraper_year = str(year)[1:-1].replace("'", "").replace(",", "-")

        except IndexError:
            scraper_year = 0

        #  bday
        try:
            w = requests.get(
                "https://en.wikipedia.org/wiki/{}".format(artist_id).replace(" ", "_")
            )
            soupW = BeautifulSoup(w.content, "lxml")

            bdayHTML = soupW.find_all("span", class_="bday")

            bday = re.findall(r"(\d{4})[-](\d{2})[-](\d{2})", str(bdayHTML))
            scraper_bday = (
                str(bday)[1:-1]
                .replace("(", "")
                .replace(")", "")
                .replace("'", "")
                .replace(",", "-")
            )

            if not len(scraper_bday):
                scraper_bday = 0

        except IndexError:
            scraper_bday = 0
            logger.info("scraper_bday - error")

        # Lyrics
        try:
            lyrics_song = lyrics(song_name, artist_id)
            print(lyrics_song)

        except IndexError:
            lyrics_song = 0

        # Generate the row
        song_element = {
            "song_id": song_id,
            "song_name": song_name,
            "img": song_img,
            "duration_ms": song_duration,
            "song_explicit": song_explicit,
            "url": song_url,
            "popularity": song_popularity,
            "date_time_played": date_time_played,
            "album_id": album_id,
            "artist_id": artist_id,
            "scrape1": scraper_year,
            "scraper2": scraper_bday,
        }

        song_list.append(song_element)

        lyrics_element = {
            "song_id": song_id,
            "song_name": song_name,
            "date_time_played": date_time_played,
            "lyrics": lyrics_song,
        }
        lyrics_list.append(lyrics_element)

    song_df = pd.DataFrame.from_dict(song_list)
    lyrics_df = pd.DataFrame.from_dict(lyrics_list)

    if pd.Series(song_df["date_time_played"]).is_unique:
        pass
    else:
        raise Exception("Primary Key check is violated")

    song_df["date_time_played"] = pd.to_datetime(song_df["date_time_played"])

    if song_df.isnull().values.any():
        raise Exception("Null values found")

    # Save in data folder
    logger.info("Writing CSV file...")
    song_df.to_csv("data/db_etl.csv")
    lyrics_df.to_csv("data/lyrics_etl.csv")

    return


if __name__ == "__main__":
    spotify_etl_func()
