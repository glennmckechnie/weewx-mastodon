mastodon - weewx extension that sends data to Mastodon
Copyright 2014-2020 Matthew Wall
Distributed under the terms of the GNU Public License (GPLv3)

Copyright Glenn McKechnie 2022 (mastodon changes)

===============================================================================

**27th Dec 2022**

Repackaged as wxtoot.py to prevent confusion with all the Mastodon references
(modules, servers, functions etc)

Now using the Mastodon module to standarize methods and simplify maintenance!?

===============================================================================
Pre-requisites

This runs under WeeWX 4.x versions, using python3. Anything else is untested.


Generate an access token on your mastodon server of choice.


Install the Python wrapper for Mastodon.
The source is at https://github.com/halcy/Mastodon.py

pip3 install Mastodon.py


===============================================================================
Installation instructions

1) download

wget -O weewx-mastodon.zip https://github.com/glennmckechnie/weewx-mastodon/archive/refs/heads/main.zip

2) run the installer:

wee_extension --install weewx-mastodon.zip

3) install the prerequisite

pip3 install Mastodon.py

4) complete the [Mastodon] section under weewx.conf

A default install will run once the 'key_access_token' and 'server_url_mastodon'
are completed correctly.
The rest is up to you

[StdRESTful]
    [[Mastodon]]
         # from your account under preferences/development/application
        key_access_token = 'replace_me'
        server_url_mastodon = 'replace_me'
         # simple , full, template
        format_choice = full
         # Mastodon will rate limit when excessive requests are made
        post_interval = 3600
         # convert from numeric degrees to Cardinal points - true or false
        cardinal = true
         # complete if fetching an image via a webserver
        server_url_image = ''
         # complete if uploading images from a local directory
        image_directory = ''
         # example: /var/www/html/weewx/DATA/mastodon.txt
        template_file =  'replace_me if using template'


5) Optional, install the templates directory and complete skin.conf to suit

6) restart weewx

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start


===============================================================================
Options

For configuration options and details, see the comments in wxtoot.py
as follows...

"""
toot weather data

You must first obtain an access token in order to toot.  See the
mastodon developer documentation to obtain these:

Visit the account you are going to post to.
Open the Preferences lik on the accounts home page, scroll down to the
'development' link and open that page.

The page will be Headed Your Applications. Here you will create a new
Application dedicated to weewx-posting.

Click 'New Application' and complete the required fields  You can accept the
defaults but you only need 'write' access. Upon completion , Save it and then
reopen it and copy "Your access token".

You need two things:  that access_token, and the mastodon_url and they will be
entered into weewx.conf at ....

[StdRESTful]
    [[Mastodon]]
        key_access_token = "Your access token"
        server_url_mastodon = "The mastodon url"

after that, the rest is optional

'simple' toots look something like this:

STATION_IDENTIFIER: Ws: 0.0; Wd: -; Wg: 1.1; oT: 7.00;
                    oH: 97.00; P: 1025.307; R: 0.000

'full' toots (the default) look like this:

STATION_IDENTIFIER:
 Winddir: N
 Windgust: 4.9 mps
 outTemp: 38.4 C
 outHumidity: 41.95 %
 Pressure: 1014.587 mbar
 Rain: 0.000 mm
 Date Time: 27 Dec 2022 18:06

The STATION_IDENTIFIER is the first part of the station 'location' defined in
weewx.conf.  To specify a different identifier for tweets, use the 'station'
parameter.  For example:

[StdRESTful]
    [[Mastodon]]
        station = hal

The 'format' parameter determines the tweet contents.

Besides specifying a format, there are 3 coded options to choose from
[StdRESTful]
    [[Mastodon]]
        format_choice = full  # simple , full, template
The 'full' format is:

format = '{station:%s} ' \
         '\n Windspeed: {windSpeed:%.1f} ' \
         '\n Winddir: {windDir:%03.0f} ' \
         '\n Windgust: {windGust:%.1f} ' \
         '\n outTemp: {outTemp:%.1f} ' \
         '\n outHumidity: {outHumidity:%.2f} ' \
         '\n Pressure: {barometer:%.3f} ' \
         '\n Rain: {rain:%.3f} ' \
         '\n Date Time: {dateTime:%d %b %Y %H:%M}'

The 'simple' format is:

format = {station:%.8s}: Ws: {windSpeed:%.1f}; Wd: {windDir:%03.0f};
         Wg: {windGust:%.1f}; oT: {outTemp:%.1f}; oH: {outHumidity:%.2f};
         P: {barometer:%.3f}; R: {rain:%.3f}

The 'template' option allows the user to take full control of the layout in
the format of a weewx style template.
See the template directory and notes written there.

To specify a different tweet message, use the format parameter.  For example,
this would tweet only wind information:

[StdRESTful]
    [[Mastodon]]
        format = {station}: Ws: {windSpeed}; Wd: {windDir}; Wg: {windGust}

If there is no value for an observation, the hyphen (-) will display.  If
the observation does not exist, the observation label will not be replaced.
If no format is specified for an observation, the default is used.
For example:

    Ws: {windSpeed}             ->  Ws: 12.3452343
    Ws: {windSpeed:%.3f}        ->  Ws: 12.345

The dateTime field is handled slightly differently.  For example:

    ts: {dateTime}              ->  ts: 1413994070
    ts: {dateTime:%X}           ->  ts: 16:07:50 22 Oct 2014
    ts: {dateTime:%H:%M:%S}     ->  ts: 16:07:50
"""