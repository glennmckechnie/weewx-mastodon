# installer for Mastodon (Mstdn)
# Copyright 2014-2020 Matthew Wall
# Distributed under the terms of the GNU Public License (GPLv3)
#
# Repurposed from twitter to Mastodon (Mstdn)
# Copyright 2022 Glenn McKechnie : glenn.mckechnie@gmail.com

try:
    # Python 2
    from StringIO import StringIO
except ImportError:
    # Python 3
    from io import StringIO

import configobj
from weecfg.extension import ExtensionInstaller

wxtoot_config = """
    [StdRESTful]
        [[Mastodon]]
        # from your account under preferences/development/application
        key_access_token = 'replace_me'
        server_url_mastodon = 'replace_me'
        # Mastodon will rate limit when excessive requests are made
        #post_interval = 3600
        # convert from numeric degrees to Cardinal points - true or false
        #cardinal = true
        # complete if fetching images via a webserver
        #server_url_image = ''
        # complete if uploading images from a local directory
        #image_directory = ''
        # comma separated list of up to 4 images
        #images = ''
        # example: /var/www/html/weewx/DATA/mastodon.txt
        #template_file = '/var/www/html/weewx/DATA/mastodon.txt'
        #template_last_file = '/var/www/html/weewx/DATA/mastsummary.txt'
        # post formats - simple, full, template
        format_choice = full
        # must finish with a valid entry as the last entry cannot be a comment
        # It disappears!

"""

wxtoot_dict = configobj.ConfigObj(StringIO(wxtoot_config))


def loader():
    return MstdnInstaller()


class MstdnInstaller(ExtensionInstaller):
    def __init__(self):
        super(MstdnInstaller, self).__init__(
            version="0.04",
            name='wxtoot',
            description='toot weather data',
            author="Glenn McKechnie",
            author_email="glenn.mckechnie@gmail.com",
            restful_services='user.wxtoot.Toot',
            config=wxtoot_dict,
            files=[
                   ('bin/user',
                    ['bin/user/wxtoot.py',
                     'bin/user/since.py']),
                   ('skins/Seasons/DATA',
                    ['skins/Seasons/DATA/mastodon.txt.tmpl',
                     'skins/Seasons/DATA/mastsummary.txt.tmpl',
                     'skins/Seasons/DATA/mastodon-skin.conf',
                     ])
                   ]
        )
