mastodon - weewx extension that sends data to Mastodon
Copyright 2014-2020 Matthew Wall
Distributed under the terms of the GNU Public License (GPLv3)

Copyright Glenn McKechnie 2022 (mastodon changes)

===============================================================================

Currently - this is in ALPHA - or a vague handwaving BETA condition.

You're more than welcome (encouraged) to download and use it - then
report back on any crashes / bugs / enhancements that may be required.

Just remember that the pieces are always yours.

Otherwise - wait a while...  About the length of a piece of string
while. :-)

See the comments in mastodon.py on how to set this up - get a key etc.


===============================================================================
Pre-requisites

Generate an access token on your mastodon server of choice



===============================================================================
Installation instructions

1) download

wget -O weewx-mastodon.zip https://github.com/glennmckechnie/weewx-mastodon/archive/refs/heads/main.zip

2) run the installer:

wee_extension --install weewx-mastodon.zip

3) modify weewx.conf:

[StdRESTful]
    [[Mastodon]]
         access_token = your_token_from_preferences/development
         mastodon_url = https://mastodon_servers_name/
         post_interval = 3600
         format_choice = full
         cardinal = true

4) restart weewx

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start


===============================================================================
Options

For configuration options and details, see the comments in mastodon.py
