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
        key_access_token = 'replace_me'  # your access_token
        server_url_mastodon = 'replace_me'
        format_choice = full  # simple , full, template
        post_interval = 3600
        cardinal = true
        server_url_image = ''  # complete if fetching images
        image_directory = ''  # complete if uploading images
        template_file =  'replace_me if using template'  # /var/www/html/weewx/DATA/mastodon.txt
"""

wxtoot_dict = configobj.ConfigObj(StringIO(wxtoot_config))


def loader():
    return MstdnInstaller()


class MstdnInstaller(ExtensionInstaller):
    def __init__(self):
        super(MstdnInstaller, self).__init__(
            version="0.02",
            name='wxtoot',
            description='toot weather data',
            author="Glenn McKechnie",
            author_email="glenn.mckechnie@gmail.com",
            restful_services='user.wxtoot.Toot',
            config=wxtoot_dict,
            files=[('bin/user', ['bin/user/wxtoot.py'])]
        )
