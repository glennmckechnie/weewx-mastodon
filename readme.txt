twitter - weewx extension that sends data to Twitter
Copyright 2014-2020 Matthew Wall
Distributed under the terms of the GNU Public License (GPLv3)

===============================================================================
Pre-requisites

Install the twitter python bindings

For python3:

sudo pip3 install twython

For python2:

sudo pip install twython


===============================================================================
Installation instructions

1) download

wget -O weewx-twitter.zip https://github.com/matthewwall/weewx-twitter/archive/master.zip

2) run the installer:

wee_extension --install weewx-twitter.zip

3) modify weewx.conf:

[StdRESTful]
    [[Twitter]]
        app_key = APP_KEY
        app_key_secret = APP_KEY_SECRET
        oauth_token = OAUTH_TOKEN
        oauth_token_secret = OAUTH_TOKEN_SECRET

4) restart weewx

sudo /etc/init.d/weewx stop
sudo /etc/init.d/weewx start


===============================================================================
Options

For configuration options and details, see the comments in twitter.py
