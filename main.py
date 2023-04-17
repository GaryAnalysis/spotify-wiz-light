import asyncio
import json
import time
from pywizlight import wizlight, PilotBuilder, discovery
import urllib.request
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from PIL import Image
import numpy as np
import os
import csv
from pathlib import Path

"""
You will need to set the following environment variables:
 - SPOTIPY_CLIENT_ID (This is your client ID, provided by Spotify at https://developer.spotify.com/)
 - SPOTIPY_CLIENT_SECRET (This is your client secret, provided by Spotify at https://developer.spotify.com/)
 - SPOTIPY_USER (This is your Spotify username, you can find this at account overview on spotify.com)
 - SPOTIPY_REDIRECT_URI (Redirect URI, e.g. http://localhost:8888/callback)
"""

# You can find your light's IP by running "find_ip.py"
wiz_ip = "IP"

# Defaults the location of the csv file to "User\Documents" for Windows, Linux and Mac. The location can be changed by changing the "filepath" variable.
home = str(Path.home())
folder_path = (home + "\Documents\Spotify to Wiz Light")
temp_path = (folder_path + "\Temporary")
csv_filepath = (folder_path + "\Spotify to Wiz Light database.csv")

# Checks if the folders and the csv file exist, creates them if it doesn't.
folder_exists = os.path.exists(folder_path)
if folder_exists == False:
    os.mkdir(folder_path)

temp_exists = os.path.exists(temp_path)
if temp_exists == False:
    os.mkdir(temp_path)
else: # Clears the temporary files
    temp_files = "{0}\*".format(temp_path)
    for t in temp_files:
        os.remove(t)

file_exists = os.path.exists(csv_filepath)
if file_exists == False:
    with open(csv_filepath, "w") as csv_file1:
        fieldnames = ["album_id", "rgb"]
        writer = csv.DictWriter(csv_file1, fieldnames=fieldnames, delimiter=",", lineterminator='\n')
        writer.writeheader()

scope = "user-read-playback-state user-read-currently-playing"
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

async def lights_on(light_rgb):
    light = wizlight(wiz_ip)
    if light_rgb == (255, 255, 255):
        await light.turn_on(PilotBuilder(cold_white=255)) # "cold_white" results in a nicer white color than using the RGB code (255, 255, 255).
        await light.turn_on(PilotBuilder(brightness=255))
    else:
        await light.turn_on(PilotBuilder(rgb=(light_rgb)))
        await light.turn_on(PilotBuilder(brightness=255))

# Variables "last_id" and "new_id" are used to check when the user skips to a different album.
last_id = None
new_id = None

while (True):
    if last_id == None and new_id == None:
        results = sp.current_playback()

        if results == None:
            time.sleep(1) # Waits one second if no song is being played.
        else:
            image_640_url = results['item']['album']['images'][0]['url'] # Obtains the (640x640) image url from Spotify.
            new_id = results['item']['album']['id'] # Obtains the album id.

            csv_album_id_list = []
            csv_rgb_list = []

            # Opens .csv "database" to check whether an album has already been played.
            with open(csv_filepath) as csv_file2:
                csv_data = csv.reader(csv_file2, delimiter=",")
                for row in csv_data:
                    csv_album_id_list.append(row[0])
                    csv_rgb_list.append(row[1])

            if new_id in csv_album_id_list: # If the album has already been played it changes the light's color.
                dominant_color2 = eval(csv_rgb_list[csv_album_id_list.index(new_id)])
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(lights_on(dominant_color2))
                loop.close()
            else: # If the album hasn't been played the image has to be processed (this takes longer time).
                urllib.request.urlretrieve(image_640_url, "{0}/{1}.png".format(temp_path, new_id)) # Saves the album image.
                image_original = Image.open("{0}/{1}.png".format(temp_path, new_id)).convert("RGB")
                image_original2 = Image.open("{0}/{1}.png".format(temp_path, new_id)).convert("RGB")
                width = image_original.size[0]
                height = image_original.size[1]

                # Each pixel of the image is processed.
                for i in range(0, width):
                    for j in range(0, height):
                        data = image_original.getpixel((i, j))

                        # This function changes each RGB value to either 0, 126 or 255.
                        def color_change():
                            rgb_value = data

                            counter = 1

                            for color in rgb_value:
                                if 0 <= color <= 62:
                                    new_value = 0
                                if 63 <= color <= 189:
                                    new_value = 126
                                if 190 <= color <= 255:
                                    new_value = 255

                                if counter == 1:
                                    new_red = new_value
                                if counter == 2:
                                    new_green = new_value
                                if counter == 3:
                                    new_blue = new_value

                                counter += 1

                            global new_rgb_value
                            new_rgb_value = (new_red, new_green, new_blue)

                        color_change()
                        image_original.putpixel((i, j), new_rgb_value) # Applies the new RGB values to the image

                image_original.save("{0}/{1} 27 colors.png".format(temp_path, new_id))
                image_27 = Image.open("{0}/{1} 27 colors.png".format(temp_path, new_id))

                # Black pixels need to be counted and then removed from the list of colors as the WiZ light can not display black light (obviously).
                black = 0
                for pixel in image_27.getdata():
                    if pixel == (0, 0, 0):
                        black += 1
                pixels = image_27.getcolors(27)
                sorted_pixels = sorted(pixels, key=lambda t: t[0])
                black_value = (black, (0, 0, 0))
                sorted_pixels.remove(black_value)

                if sorted_pixels == []: # If the album cover is entirely black (when using 27 colors)
                    print("DONDA")
                else:
                    dominant_color = sorted_pixels[-1][1]

                    # Creates a list that has the minimum and maximum values for the dominant color, in order.
                    range_list = []

                    for value in dominant_color:
                        if value == 0:
                            range_list.extend((0, 62))
                        if value == 126:
                            range_list.extend((63, 189))
                        if value == 255:
                            range_list.extend((190, 255))

                    # If the color isn't in the dominant color range, it is painted over with black.
                    for i in range(0, width):
                        for j in range(0, height):
                            data = image_original2.getpixel((i, j))

                            # Uses the values from "range_list" to define the colors that should NOT be eliminated.
                            changedata = (range_list[0] <= data[0] <= range_list[1] and
                                          range_list[2] <= data[1] <= range_list[3] and
                                          range_list[4] <= data[2] <= range_list[5])

                            if changedata:
                                pass
                            else:
                                image_original2.putpixel((i, j), (0, 0, 0))

                    # The "mic" or "most important color" image is saved.
                    image_original2.save("{0}/{1} mic.png".format(temp_path, new_id))
                    image_mic = Image.open("{0}/{1} mic.png".format(temp_path, new_id))

                    # Black pixels need to be counted and then removed, just like previously.
                    black2 = 0
                    for pixel in image_mic.getdata():
                        if pixel == (0, 0, 0):
                            black2 += 1

                    # This time the amount of colors that need to be retrieved isn't restricted to 27 colors.
                    # Because every pixel could have a different color, the ".getcolors" function is used for all non-black pixels.
                    pixels2 = image_mic.getcolors(width * height - black2)

                    sorted_pixels2 = sorted(pixels2, key=lambda t: t[0])
                    black_value2 = (black2, (0, 0, 0))
                    sorted_pixels2.remove(black_value2)

                    dominant_color2 = sorted_pixels2[-1][1] # Retrieves the most used color among the dominant colors. This value is then used for the light.
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(lights_on(dominant_color2))
                    loop.close()

                    # The color used for this album is then appended to a .csv file. This is done to minimize wait times.
                    with open(csv_filepath, "a", newline="") as csv_file3:
                        writer = csv.writer(csv_file3, delimiter=",", lineterminator="\n")
                        written_data = (new_id, dominant_color2)
                        writer.writerow(written_data)

    if last_id == None and new_id != None:
        last_id = new_id
        results = sp.current_playback()
        new_id = results['item']['album']['id']
    
    if last_id != None and new_id != None:
        if new_id == last_id:
            last_id = None
            results = sp.current_playback()
            new_id = results['item']['album']['id']
        else:
            last_id = None
            new_id = None