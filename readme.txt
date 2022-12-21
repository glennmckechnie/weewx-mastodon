twitter - weewx extension that sends data to Twitter
Copyright 2014-2020 Matthew Wall
Distributed under the terms of the GNU Public License (GPLv3)

Copyright Glenn McKechnie 2022 (mastodon changes)

===============================================================================
Pre-requisites

Geberate an access token on your mastodon server of choice



===============================================================================
Installation instructions

1) download

wget -O weewx-mastodon.zip https://github.com/matthewwall/weewx-mastodon/archive/main.zip

2) run the installer:

wee_extension --install weewx-mastodon.zip

3) modify weewx.conf:

[StdRESTful]
    [[Mastodon]]
         access_token = your_token_from_preferences/development
         mastodon_url = https://mastodon_servers_name/
         post_interval = 300
         format_choice = simple

4) restart weewx

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start


===============================================================================
Options

For configuration options and details, see the comments in twitter.py
