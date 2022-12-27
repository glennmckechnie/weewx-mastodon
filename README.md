
# mastodon (wxtoot)

## A weewx extension that sends data to a Mastodon social networking site

Copyright 2014-2020 Matthew Wall

Distributed under the terms of the GNU Public License (GPLv3)

Copyright Glenn McKechnie 2022 (mastodon changes)


![https://mastodon.au/@BroomfieldWeatherBot](https://github.com/glennmckechnie/weewx-mastodon/blob/main/weewx-mastodon-V0_2.png "weewx-mastodon bot output") 

* The above screenshot ([from this site](https://mastodon.au/@BroomfieldWeatherBot)) shows 4 images, one of which is the output of [weewx-wxgraphic](https://github.com/glennmckechnie/weewx-WXgraphic)

* The text is from the default stanza - 'full'. It has images included via further (optional) configuration.

* There is a much simpler example of the text  - 'simple' 

* There is also the ability to put together your own 'format' string into weewx.conf and overide the others.

* The final option is to use a template generated by a weewx skin - an example is provided that fits the Seasons skin. It is portable (and configurable)  though.

This [weewx-user thread](https://groups.google.com/g/weewx-user/c/wo26pKJ9q9I/m/x0DtYomXBQAJ) started this process. Visit it for other examples and for the templates source :-)

The base code is from the weewx twitter extension. So if you've used that, then this will be very familiar in its setup.

----
**27th Dec 2022**

version V0.2

Repackaged as wxtoot.py to prevent confusion with all the Mastodon references
(modules, servers, functions etc)

Now using the Mastodon module to standarize methods and simplify maintenance!?

Up to 4 images can be uploaded. That's the first 4 it finds in the image directory; although the server_url_image (wxgraphic in this case) counts as one and gets priority.

I have tested it and it works for me. If you find it doesn't work for you then raise an issue here - or visit weewx-user (see the link above).

As always, suggestions, fixes, bugs, then contact me. 

----

***Pre-requisites***

This runs under WeeWX 4.x versions, using python3. Anything else is untested.

You need to generate an access token on your mastodon server of choice. (see below)

Install the Python wrapper for Mastodon.
That source is at https://github.com/halcy/Mastodon.py

<pre>pip3 install Mastodon.py</pre>


----

***Installation instructions***

1) download

<pre>wget -O weewx-mastodon.zip https://github.com/glennmckechnie/weewx-mastodon/archive/refs/heads/main.zip</pre>

2) run the installer:

<pre>wee_extension --install weewx-mastodon.zip</pre>

3) install the prerequisite

<pre>pip3 install Mastodon.py</pre>

4) complete the [Mastodon] section under weewx.conf

A default install will run when the 'key_access_token' and 'server_url_mastodon'
are completed correctly.
Refining that initial configuration is then your choice.
<pre>
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
</pre>

5) Optional, install the templates directory and complete skin.conf to suit.

6) restart weewx

<pre>
sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start
</pre>

----

***Options***

For configuration options and details, see the comments in wxtoot.py;
which currently are as follows... but firstly.

You are creating a bot. Play nicely. 

The default post_interval is 3600 seconds (1 hour). You can change it.

You can make it longer (more resources for other users) or make it less (fewer resources...) Keep in mind the bot is posting constantly, no sleep, no rest, no lull. It's a compromise and the aim is to avoid the [Tragedy of the commons](https://en.wikipedia.org/wiki/Tragedy_of_the_commons)

<pre>
toot weather data

You must first obtain an access token in order to toot.  See the
mastodon developer documentation to obtain these:

Login to the account you are going to post to.
Open the Preferences link on the accounts home page, scroll down to the
'development' link and open that page.

The page will be headed Your Applications. Here you will create a new
Application dedicated to weewx-mastodon.

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
weewx.conf.  To specify a different identifier for toots, use the 'station'
parameter.  For example:

[StdRESTful]
    [[Mastodon]]
        station = hal

The 'format' parameter determines the toot contents.

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

To specify a different toot message via weewx.conf, use the format parameter.
For example, this would toot only wind information:

[StdRESTful]
    [[Mastodon]]
        format = {station}: Ws: {windSpeed}; Wd: {windDir}; Wg: {windGust}

Finally. The 'template' option allows the user to take full control of the
layout in the format of a weewx style template.
See the template directory and notes written there.


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
</pre>
