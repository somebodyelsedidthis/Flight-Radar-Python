import csv
import os
import time
import urllib.request

import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from opensky_api import OpenSkyApi, TokenManager
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from adjustText import adjust_text
import geocoder
import matplotlib.animation as anim

api = OpenSkyApi(token_manager=TokenManager.from_json_file('credentials.json'))

LAT_HAM = 1.386068
LON_HAM = 103.841097

LAT_ANNIE = 1.382789
LON_ANNIE = 103.749806

LAT_NED = 52.074272
LON_NED = 4.318774

g = geocoder.ip('me')
LAT_IP = g.latlng[0]
LON_IP = g.latlng[1]

SAVED_LOCATIONS = {
    '1': (LAT_IP, LON_IP, 'Current Location'),
    '2': (LAT_HAM, LON_HAM, 'Soham'),
    '3': (LAT_ANNIE, LON_ANNIE, 'Annie'),
    '4': (LAT_NED, LON_NED, 'Delft House')
}

lon_self = LON_IP
lat_self = LAT_IP
curent_loc_key = '1'

RADIUS_DEG = 1.0
AIRPORT_TYPES = {'large_airport', 'medium_airport', 'small_airport'}

AIRPORTS_CSV_URL = 'https://davidmegginson.github.io/ourairports-data/airports.csv'
AIRPORTS_CSV_PATH = 'airports.csv'

def get_aerodrome_data(lat_center, lon_center, radius_deg=RADIUS_DEG, airport_types=None):
    if airport_types is None:
        airport_types = AIRPORT_TYPES

    if not os.path.exists(AIRPORTS_CSV_PATH):
        urllib.request.urlretrieve(AIRPORTS_CSV_URL, AIRPORTS_CSV_PATH)

    aerodromes = []
    aerodrome_labels = []

    with open(AIRPORTS_CSV_PATH, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            if row['type'] not in airport_types:
                continue
            if not row['ident'] or not row['latitude_deg'] or not row['longitude_deg']:
                continue

            lat = float(row['latitude_deg'])
            lon = float(row['longitude_deg'])

            if abs(lat - lat_center) <= radius_deg and abs(lon - lon_center) <= radius_deg:
                aerodromes.append((lon, lat))
                
                label = row['icao_code'] if row['icao_code'] else row['ident']
                aerodrome_labels.append(label)

    return aerodromes, aerodrome_labels

def coordinates():
    lon = []
    lat = []
    flight = []
    raw_states = []

    try:
        states = api.get_states(bbox=(lat_self-RADIUS_DEG, lat_self+RADIUS_DEG, lon_self-RADIUS_DEG, lon_self+RADIUS_DEG))

    except Exception as e:
        print(f"[DEBUG]Error fetching states from OpenSky API: {e}")
        return [], [], [], []    

    if states is None:
        print("[DEBUG] api.get_states() returned None")
        return [], [], [], []

    if states.states is None:
        print("[DEBUG] No state data available from OpenSky API.")
        return [], [], [], []

    for s in states.states:
        lon.append(s.longitude)
        lat.append(s.latitude)
        flight.append(s.callsign.strip() if s.callsign else 'N/A')
        raw_states.append(s)

#    print(f"[DEBUG] fetched {len(raw_states)} aircraft")
    return(lon,lat,flight,raw_states)

aerodromes, aerodrome_labels = get_aerodrome_data(lat_self, lon_self)

plt.style.use('dark_background')

fig, ax = plt.subplots(figsize=(15, 15), subplot_kw={'projection': ccrs.PlateCarree()})


current_states = []

#detail_box = ax.annotate('', xy=(0,0), xytext=(20,20), textcoords='offset points', bbox=dict(boxstyle='round,pad=0.5', fc='black', ec='cyan', alpha=0.9), color='white', fontfamily='monospace', fontsize=9, zorder=10, visible=False)

def format_flight_details(s):
    callsign = s.callsign.strip() if s.callsign else 'N/A'
    alt_m = s.geo_altitude if s.geo_altitude is not None else s.baro_altitude if s.baro_altitude is not None else 'N/A'
    alt_ft = f'{alt_m * 3.28084:.0f} ft' if alt_m is not None else 'N/A'
    speed = s.velocity if s.velocity is not None else 'N/A'
    heading = f"{s.true_track:.0f}°" if s.true_track is not None else 'N/A'
    vrate = f"{s.vertical_rate:.1f} m/s" if s.vertical_rate is not None else 'N/A'
    status = 'On ground' if s.on_ground else 'Airborne'

    return (
        f"Callsign : {callsign}\n"
        f"ICAO24   : {s.icao24}\n"
        f"Country  : {s.origin_country}\n"
        f"Status   : {status}\n"
        f"Altitude : {alt_ft}\n"
        f"Speed    : {speed}\n"
        f"Heading  : {heading}\n"
        f"V/Rate   : {vrate}"
    )

def on_pick(event):
#    print(f"[DEBUG] pick_event fired: artist={event.artist}, ind={getattr(event, 'ind', None)}")


    if event.artist not in aircraft_artists:
#        print("[DEBUG] artist not in aircraft_artists, ignoring")
        return
    if not event.ind.size:
#        print("[DEBUG] event.ind empty, ignoring")
        return
    
    idx = event.ind[0]
#    print(f"[DEBUG] on_pick sees current_states len={len(current_states)}, id={id(current_states)}")
    if idx >= len(current_states):
#        print(f"[DEBUG] idx {idx} out of range for current_states (len={len(current_states)})")
        return
    
    s = current_states[idx]
    detail_box.xy = (s.longitude, s.latitude)
    detail_box.set_text(format_flight_details(s))
    detail_box.set_visible(True)
    detail_box._icao24 = s.icao24
    on_pick.just_picked = True
#    print(f"[DEBUG] showing detail box for {s.icao24}")
    fig.canvas.draw_idle()

on_pick.just_picked = False

def on_click(event):
#    print(f"[DEBUG] button_press_event fired: inaxes={event.inaxes}, xdata={event.xdata}, ydata={event.ydata}")

    if on_pick.just_picked:
        on_pick.just_picked = False
        return
    if event.inaxes != ax:
        return
    detail_box.set_visible(False)
    fig.canvas.draw_idle()

fig.canvas.mpl_connect('pick_event', on_pick)
fig.canvas.mpl_connect('button_press_event', on_click)

def draw_static_background():
    global detail_box, title_artist

    ax.clear()

    ax.set_extent([lon_self - RADIUS_DEG, lon_self + RADIUS_DEG, lat_self - RADIUS_DEG, lat_self + RADIUS_DEG], crs=ccrs.PlateCarree())

    ax.add_feature(cfeature.LAND.with_scale('10m'), color='#1a1a1a')
    ax.add_feature(cfeature.OCEAN.with_scale('10m'), color='#0d0d2b')
    ax.add_feature(cfeature.COASTLINE.with_scale('10m'), linewidth=0.8, edgecolor='white')
    ax.add_feature(cfeature.BORDERS.with_scale('10m'), linewidth=0.5, edgecolor='grey')

    ax.scatter(lon_self, lat_self, color='red', s=100, zorder=5, transform=ccrs.PlateCarree())

    ax.scatter([lon for lon, lat in aerodromes], [lat for lon, lat in aerodromes], marker='2', color='olive', s=100, zorder=5, transform=ccrs.PlateCarree())

    aerodrome_texts = [ax.text(lon, lat, label, ha='center', va='center', color='olive', fontfamily='monospace', fontname='Courier New', transform=ccrs.PlateCarree(), zorder=6) for (lon, lat), label in zip(aerodromes, aerodrome_labels)]
    if aerodrome_texts:
        adjust_text(aerodrome_texts, ax=ax, arrowprops=dict(arrowstyle='->', color='olive'), zorder=6)
    
    ax.gridlines(color='green', alpha=0.5, zorder=4, draw_labels=False)

    detail_box = ax.annotate('', xy=(0,0), xytext=(20,20), textcoords='offset points', bbox=dict(boxstyle='round,pad=0.5', fc='black', ec='cyan', alpha=0.9), color='white', fontfamily='monospace', fontsize=9, zorder=10, visible=False)

    location_name = SAVED_LOCATIONS[curent_loc_key][2]

    title_artist = ax.set_title(f'Live Local Aircraft Tracker - {location_name}', color='white')

draw_static_background()

#title_artist = ax.set_title('Live Local Aircraft Tracker', color='white')

aircraft_artists = []

def switch_location(key):
    global lat_self, lon_self, current_location_key, aerodromes, aerodrome_labels, aircraft_artists, current_states

    if key not in SAVED_LOCATIONS:
        return
    
    if key == curent_loc_key:
        return
    
    new_lat, new_lon, _ = SAVED_LOCATIONS[key]
    lat_self = new_lat
    lon_self = new_lon
    current_location_key = key

    aerodromes, aerodrome_labels = get_aerodrome_data(lat_self, lon_self)

    aircraft_artists = []
    current_states = []

    draw_static_background()
    fig.canvas.draw_idle()

def on_key(event):
    if event.key in SAVED_LOCATIONS:
        switch_location(event.key)

fig.canvas.mpl_connect('key_press_event', on_key)

location_buttons = []
num_locations = len(SAVED_LOCATIONS)
button_width = 0.15
button_gap = 0.02
start_x = 0.5 - (num_locations * button_width + (num_locations - 1) * button_gap) / 2

for i, (key, (_, _, name)) in enumerate(SAVED_LOCATIONS.items()):
    btn_ax = fig.add_axes([start_x + i * (button_width + button_gap), 0.01, button_width, 0.04])
    btn = Button(btn_ax, f'{key}: {name}', color='#222222', hovercolor='#444444')
    btn.label.set_color('white')
    btn.on_clicked(lambda event, k=key: switch_location(k))
    location_buttons.append(btn)

def draw_frame(frame):
    global aircraft_artists, current_states

    for artist in aircraft_artists:
        artist.remove()
    aircraft_artists = []

    lon, lat, flight, raw_states = coordinates()
    current_states = raw_states
#    print(f"[DEBUG] draw_frame set current_states, len={len(current_states)}, id={id(current_states)}")

    scatter = ax.scatter(lon, lat, color='green', zorder=6, transform=ccrs.PlateCarree(), picker=True, pickradius=5)
    aircraft_artists.append(scatter)

    texts = [ax.text(lon[i], lat[i], label, ha='center',va='center', color='green', fontfamily='monospace', fontname='Courier New', transform=ccrs.PlateCarree(), zorder=6) for i, label in enumerate(flight)]
    if texts:
        adjust_text(texts, ax=ax, zorder=6)
    aircraft_artists.extend(texts)


    if detail_box.get_visible():
        match = next(
            (s for s in current_states if s.icao24 == getattr(detail_box, '_icao24', None)),
            None   
        )

        if match is None:
            detail_box.set_visible(False)
        else:
            detail_box.xy = (match.longitude, match.latitude)
            detail_box.set_text(format_flight_details(match))


    title_artist.set_text(f'Live Local Aircraft Tracker - Updated: {time.strftime("%H:%M:%S")}')

    return aircraft_artists + [title_artist]


ani = anim.FuncAnimation(fig, draw_frame, interval=10000, cache_frame_data=False)

plt.show()