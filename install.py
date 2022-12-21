# installer for Mastodon
# Copyright 2014-2020 Matthew Wall
# Distributed under the terms of the GNU Public License (GPLv3)
#
# Repurposed from twitter to Mastodon
# Copyright 2022 Glenn McKechnie : glenn.mckechnie@gmail.com

from weecfg.extension import ExtensionInstaller


def loader():
    return MastodonInstaller()


class MastodonInstaller(ExtensionInstaller):
    def __init__(self):
        super(MastodonInstaller, self).__init__(
            version="0.01",
            name='mastodon',
            description='toot weather data',
            author="Matthew Wall",
            author_email="glenn.mckechnie@gmail.com",
            restful_services='user.mastodon.Mastodon',
            config={
                'StdRESTful': {
                    'Mastodon': {
                        'access_token': 'Your access token',
                        'mastodon_url': 'Your Mastodon Servers URL',
                        'format_choice': 'None',
                        'post_interval': '3600'}}},
            files=[('bin/user', ['bin/user/mastodon.py'])]
        )
