#!/usr/bin/python3
# Copyright 2014-2020 Matthew Wall
# Original code was from Mathews twitter.py
#
# Re-purposed by Glenn McKechnie 20/12/2022 for Mastodon use.
# Mastodon is so close to twitter that it was a given to re-purpose this
# code.
# Mistakes are mine!

# https://github.com/halcy/Mastodon.py
# pip3 install Mastodon.py

"""
NB:
You are creating a bot. Play nicely.

The default post_interval is 3600 seconds (1 hour). You can change it.

You can make it longer (more resources for other users) or make it less (fewer
resources...) Keep in mind the bot is posting constantly, no sleep, no rest, no
lull. It's a compromise and the aim is to avoid the Tragedy of the commons.

toot weather data

You must first obtain an access token in order to toot.  See the
mastodon developer documentation to obtain these:

Login to the account you are going to post to.
Open the Preferences link on the accounts home page, scroll down to the
'development' link and open that page.

The page will be headed Your Applications. Here you will create a new
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

To specify a different toot message, use the format parameter.  For example,
this would toot only wind information:

[StdRESTful]
    [[Mastodon]]
        format = {station}: Ws: {windSpeed}; Wd: {windDir}; Wg: {windGust}

Finally. The 'template' option allows the user to take full control of the
layout in the format of a weewx style template. Besides 'format = template' you
will also need to specify the path to the template!

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

"""

try:
    # Python 3
    import queue
except ImportError:
    # Python 2
    import Queue as queue
import os
import re
import sys
import time
import requests
import shutil
import glob
import weewx
import weewx.restx
import weewx.units
from weeutil.weeutil import to_bool
from mastodon import Mastodon

try:
    # Test for new-style weewx logging by trying to import weeutil.logger
    import weeutil.logger
    import logging
    log = logging.getLogger(__name__)

    def logdbg(msg):
        log.debug(msg)

    def loginf(msg):
        log.info(msg)

    def logerr(msg):
        log.error(msg)

except ImportError:
    # Old-style weewx logging
    import syslog

    def logmsg(level, msg):
        syslog.syslog(level, 'restx: Mastodon: %s' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)

    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)

    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)


VERSION = "0.04"

if weewx.__version__ < "3":
    raise weewx.UnsupportedFeature("weewx 3 is required, found %s" %
                                   weewx.__version__)


def _format(label, fmt, datum):
    s = fmt % datum if datum is not None else "None"
    return "%s: %s" % (label, s)


def _dir_to_ord(x, ordinals):
    try:
        return ordinals[int(round(x / 22.5))]
    except (ValueError, IndexError):
        pass
    return ordinals[17]


class Toot(weewx.restx.StdRESTbase):

    _DEFAULT_FORMAT_1 = '{station:%.8s}: Ws: {windSpeed:%.1f}; Wd:' \
                        '{windDir:%03.0f}; Wg: {windGust:%.1f};' \
                        'oT: {outTemp:%.1f}; oH: {outHumidity:%.2f};' \
                        'P: {barometer:%.3f}; R: {rain:%.3f}'

    _DEFAULT_FORMAT_2 = '{station:%s} ' \
                        '\n Windspeed: {windSpeed:%.1f} ' \
                        '\n Winddir: {windDir:%03.0f} ' \
                        '\n Windgust: {windGust:%.1f} ' \
                        '\n outTemp: {outTemp:%.1f} ' \
                        '\n outHumidity: {outHumidity:%.2f} ' \
                        '\n Pressure: {barometer:%.3f} ' \
                        '\n Rain: {rain:%.3f} ' \
                        '\n Date Time: {dateTime:%d %b %Y %H:%M}'

    _DEFAULT_MISSING  = 'Missing template file path'
    _DEFAULT_FORMAT_3 = '{station:%.8s}: Ws: {windSpeed:%.1f};' \
                        'Wd:{windDir:%03.0f}'

    _DEFAULT_FORMAT_NONE = '-'
    _DEFAULT_ORDINALS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S',
                         'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW', 'N', '-']

    def __init__(self, engine, config_dict):
        """This service recognizes standard restful options plus the following:

        Required parameters:

        mastodon authentication credentials:
        key_access_token
        server_url_mastodon

        Optional parameters:

        station: a short name to identify the weather station
        Default is the station location from [Station]

        unit_system: one of US, METRIC, or METRICWX
        Default is None; units will be those of the data in the database

        format_choice: indicates how the tweet should be rendered via the
        inbuilt defaults.
        simple contains basic weather data
        full contains the basic weather data with non abbreviated descriptions,
         new lines, ordinates for windDir and DateTime field

        format: indicates how the tweet should be rendered
        Default contains basic weather data

        format_None: indicates how a NULL value should be rendered
        Default is -

        format_utc: display time in UTC rather than local time
        Default is False

        binding: either loop or archive
        Default is archive

        https://docs.joinmastodon.org/methods/statuses/
        visibility
             String. Sets the visibility of the posted status to
             public,
             unlisted,
             private (followers only),
             direct (mentioned people only).

        cardinal: sets how to display the Ordinals for wind direction

        cardinal = True (default)
          Wd: {windDir:%03.0f}        ->  Wd: E

        cardinal = False
          Wd: {windDir:%03.0f}        ->  Wd: 090

        """
        super(Toot, self).__init__(engine, config_dict)
        loginf('service version is %s' % VERSION)

        site_dict = weewx.restx.get_site_dict(config_dict,
                                              'Mastodon',
                                              'key_access_token',
                                              'server_url_mastodon',
                                              )
        if site_dict is None:
            logerr("site_dict failed, is it complete? : %s" % site_dict)
            return

        # default the station name
        site_dict.setdefault('station', config_dict['Station']['location'])

        # FIXME potential case issue
        usn = config_dict['StdReport']['Defaults']['unit_system']
        if usn is not None:
            site_dict['unit_system'] = weewx.units.unit_constants[usn.upper()]
            loginf('unit system is %s' % usn)

        site_dict.setdefault('cardinal', True)
        site_dict['format_ordinal'] = to_bool(site_dict.get('cardinal'))
        site_dict.setdefault('format_choice', 'full')
        if site_dict['format_choice'] == 'simple':
            site_dict.setdefault('format', self._DEFAULT_FORMAT_1)
        elif site_dict['format_choice'] == 'full':
            site_dict.setdefault('format', self._DEFAULT_FORMAT_2)
        elif site_dict['format_choice'] == 'template':
            site_dict.setdefault('format', self._DEFAULT_MISSING)
        else:
            site_dict.setdefault('format', self._DEFAULT_FORMAT_3)

        site_dict.setdefault('server_url_image', '')
        site_dict.setdefault('image_directory', '')
        site_dict.setdefault('images', '')
        site_dict.setdefault('template_file', '')
        site_dict.setdefault('template_last_file', '')
        site_dict.setdefault('format_None', self._DEFAULT_FORMAT_NONE)
        site_dict.setdefault('format_utc', False)
        site_dict['format_utc'] = to_bool(site_dict.get('format_utc'))
        site_dict.setdefault('ordinals', self._DEFAULT_ORDINALS)

        site_dict.setdefault('dev_mode', False)
        site_dict['dev_mode'] = to_bool(site_dict.get('dev_mode'))
        self.dev_mode = site_dict['dev_mode']

        # The site_dict values are obfuscated when using wee_debug
        # This is only for posting log extracts - better safe than sorry!
        dict_copy = site_dict.copy()
        dict_copy['key_access_token'] = "removed for privacy"
        dict_copy['server_url_mastodon'] = "also removed for privacy"

        # visibility : options are ... public, unlisted, private, direct
        if self.dev_mode:
            # very chatty... for development only
            site_dict.setdefault('visibility', 'direct')
            site_dict.setdefault('post_interval', '60')
            loginf("final site_dict contains %s" % dict_copy)
        else:
            site_dict.setdefault('visibility', 'unlisted')
            site_dict.setdefault('post_interval', '3600')

        logdbg("site_dict is : %s" % site_dict)

        loginf("toot visibility is %s " % site_dict['visibility'])

        # we can bind to archive or loop events, default to archive
        binding = site_dict.pop('binding', 'archive')
        if isinstance(binding, list):
            binding = ','.join(binding)
        loginf('binding is %s' % binding)

        # run some prechecks
        # FIXME - probably too early, but they will be generated if allowed to
        # continue - unless user intervention is truly required
        """
        self.template_file = site_dict.get('template_file')
        if self.template_file:
            if self.dev_mode:
                loginf("template_file is %s" % self.template_file)
            if not os.path.isfile(self.template_file):
                logerr("Missing file? %s" % self.template_file)
        self.templatesum_file = site_dict.get('template_last_file')
        if self.templatesum_file:
            if self.dev_mode:
                loginf("templatesum_file is %s" % self.templatesum_file)
            if not os.path.isfile(self.templatesum_file):
                logerr("Missing summary file? %s" % self.templatesum_file)
        """
        self.image_directory = site_dict.get('image_directory')
        if self.image_directory:
            if os.path.isdir(self.image_directory):
                pass
            else:
                logerr("Error accessing directory: %s" % self.image_directory)
                return

        self.data_queue = queue.Queue()
        data_thread = TootThread(self.data_queue, **site_dict)
        data_thread.start()

        if 'loop' in binding.lower():
            self.bind(weewx.NEW_LOOP_PACKET, self.handle_new_loop)
        if 'archive' in binding.lower():
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.handle_new_archive)

        loginf("Data will be tooted for %s" % site_dict['station'])

    def handle_new_loop(self, event):
        # Make a copy... we will modify it
        packet = dict(event.packet)
        packet['binding'] = 'loop'
        self.data_queue.put(packet)

    def handle_new_archive(self, event):
        # Make a copy... we will modify it
        record = dict(event.record)
        record['binding'] = 'archive'
        self.data_queue.put(record)


class TootThread(weewx.restx.RESTThread):
    def __init__(self, queue, images, dev_mode, server_url_image,
                 image_directory, template_file, template_last_file,
                 key_access_token, server_url_mastodon, visibility,
                 cardinal, format_choice, station, format, format_None,
                 ordinals, post_interval,
                 format_utc=True, format_ordinal=True,
                 unit_system=None, skip_upload=False,
                 log_success=True, log_failure=True,
                 max_backlog=sys.maxsize, stale=None,
                 timeout=60, max_tries=3, retry_wait=5):
        super(TootThread, self).__init__(queue,
                                         protocol_name='Mastodon',
                                         manager_dict=None,
                                         post_interval=post_interval,
                                         max_backlog=max_backlog,
                                         stale=stale,
                                         log_success=log_success,
                                         log_failure=log_failure,
                                         max_tries=max_tries,
                                         timeout=timeout,
                                         retry_wait=retry_wait)

        self.mstdn = Mastodon(access_token=key_access_token,
                              api_base_url=server_url_mastodon)

        self.image_server = server_url_image
        self.image_directory = image_directory
        self.image_directory = os.path.join(self.image_directory, '')
        self.dev_mode = dev_mode
        if self.dev_mode:
            loginf("post_interval of TootThread is %s" % post_interval)
        if images:
            if type(images) is str:
                # where there is only 1 image - a str
                if self.dev_mode:
                    loginf("str images %s : type %s" % (images, type(images)))
                self.images = [images]
                if self.dev_mode:
                    loginf("now list self.images %s : type %s" % (self.images,
                                                                  images))
            else:
                # just assign the list of images
                self.images = images
        else:
            # or leave it as None
            self.images = images

        self.template_file = template_file
        self.templatesum_file = template_last_file
        self.station = station
        self.format_choice = format_choice
        self.format = format
        self.format_None = format_None
        self.visibility = visibility
        self.ordinals = ordinals
        self.format_utc = format_utc
        self.format_ordinal = format_ordinal
        self.unit_system = unit_system
        self.skip_upload = to_bool(skip_upload)
        # time (24 hours) to post yesterdays summary. Assumed to be 9 to match
        # since.py rain offset.
        self.summary_time = int(9)

        if self.format_ordinal:
            # backwards compatability with twitter method
            self.cardinal = 'ord'
        else:
            # text for degrees direction
            self.cardinal = 'deg'

    def format_toot(self, record):
        # from mqtt.py
        UNIT_REDUCTIONS = {
            'degree_F': 'F',
            'degree_C': 'C',
            'inch': 'in',
            'mile_per_hour': 'mph',
            'mile_per_hour2': 'mph',
            'km_per_hour': 'kph',
            'km_per_hour2': 'kph',
            'meter_per_second': 'mps',
            'meter_per_second2': 'mps',
            'degree_compass': None,
            'watt_per_meter_squared': 'Wpm2',
            'uv_index': None,
            'percent': '%',
            'unix_epoch': None,
        }
        msg = self.format
        for obs in record:
            oldstr = None
            fmt = '%s'
            pattern = "{%s}" % obs
            m = re.search(pattern, msg)
            if m:
                if self.dev_mode:
                    loginf("START pattern = %s in %s" % (pattern, msg))
                oldstr = m.group(0)
                if self.dev_mode:
                    loginf("  oldstr = %s" % oldstr)
            else:
                pattern = "{%s:([^}]+)}" % obs
                m = re.search(pattern, msg)
                if m:
                    oldstr = m.group(0)
                    fmt = m.group(1)
            if oldstr is not None:
                abv_unit = ' '
                if obs == 'dateTime':
                    if self.format_utc:
                        ts = time.gmtime(record[obs])
                    else:
                        ts = time.localtime(record[obs])
                    newstr = time.strftime(fmt, ts)
                elif record[obs] is None:
                    newstr = self.format_None
                elif obs == 'windDir':
                    if self.cardinal == 'ord':
                        newstr = (_dir_to_ord(record[obs], self.ordinals))
                    else:  # label in degrees
                        abv_unit = 'deg'
                elif obs == 'station':
                    newstr = fmt % record[obs]
                else:
                    (unit_type, _) = weewx.units.getStandardUnitType(
                                                 self.unit_system, obs)
                    abv_unit = UNIT_REDUCTIONS.get(unit_type, unit_type)
                    # manual overide for unconventional unit mix !
                    # FIXME
                    # if abv_unit == 'mps':
                    #     abv_unit = 'kph'
                    # elif abv_unit == 'mbar':
                    #     abv_unit = 'hPa'
                    newstr = fmt % record[obs]
                    if self.dev_mode:
                        loginf("Replace with oldstr %s : newstr  %s : abv_unit = %s " %
                               (oldstr, newstr, abv_unit))
                if self.dev_mode:
                    loginf("obs %s : record %s and unit %s" % (record[obs],
                                                               obs,
                                                               abv_unit))
                msg = msg.replace(oldstr, (newstr + ' ' + abv_unit))

        logdbg('format msg: %s' % msg)
        return msg

    def process_record(self, record, dummy_manager):
        if self.unit_system is not None:
            record = weewx.units.to_std_system(record, self.unit_system)
        record['station'] = self.station

        if self.format_choice == 'template' and self.template_file:
            ts = time.localtime()
            if ts.tm_hour == self.summary_time and self.templatesum_file:
                try:
                    with open(self.templatesum_file, 'r') as f:
                        msg = f.read()
                        msg = msg.replace("\\n", "\n")
                except Exception as e:
                    loginf("Skipping summary file, not found!")
                    logdbg("MISSING %s continuing... %s" % (
                            self.templatesum_file, e))
                    msg = "Missing summary template file"
            else:
                try:
                    with open(self.template_file, 'r') as f:
                        msg = f.read()
                        msg = msg.replace("\\n", "\n")
                except Exception as e:
                    logerr("MISSING %s continuing... %s" % (
                            self.template_file, e))
                    msg = "Missing template file"
        else:
            msg = self.format_toot(record)

        if self.skip_upload:
            loginf('skipping upload')
            return

        # now do the posting
        self.post_with_retries(msg)

    def post_with_retries(self, msg):
        ntries = 0
        while ntries < self.max_tries:
            ntries += 1
            imgs = ''
            try:
                # fetch an image from a web server
                our_images = []
                img_0 = ''
                dev_msg = 'DEV_MODE : '
                if self.image_server:
                    # Only the web server? Then put the img files in /tmp
                    if not self.image_directory:
                        self.serv_image_directory = '/tmp/'
                    else:
                        self.serv_image_directory = self.image_directory
                    image = requests.get(self.image_server, stream=True)
                    if image.status_code == 200:
                        # Set decode_content value to True, otherwise the
                        # downloaded image file's size will be zero.
                        image.raw.decode_content = True
                    img_0 = (self.serv_image_directory+'wxgraphic.png')

                    with open(img_0, 'wb') as f:
                        shutil.copyfileobj(image.raw, f)
                    our_images.append(img_0)
                    logdbg("Image server fetched %s (%s)" % (img_0, image))
                    if self.dev_mode:
                        loginf("Image server fetched %s (%s)" % (img_0, image))
                        dev_msg += ": With server image : "

                # fetch images from the local file system as named files
                if self.images and self.image_directory:
                    if self.dev_mode:
                        loginf("len of named images ... %s" % len(self.images))
                    for imgs in self.images:
                        our_images.append(self.image_directory+imgs)
                    our_images = our_images[:4]
                    if self.dev_mode:
                        loginf("our local image list is %s" % our_images)
                        dev_msg += " : With named images : "
                # or via a directory search (allows changing image names)
                elif self.image_directory:
                    if self.dev_mode:
                        loginf("image directory only")
                    self.allow_ext = '.png'
                    for imgs in glob.iglob(f'{self.image_directory}/*'):
                        if (imgs == img_0):
                            continue
                        if (imgs.endswith(".png")) or \
                           (imgs.endswith(".jpg")):
                            our_images.append(imgs)
                        elif (imgs.endswith(".gif")) or \
                             (imgs.endswith(".webp")):
                            our_images.append(imgs)
                    if self.dev_mode:
                        dev_msg += " : With unnamed images : "
                # but there can be only 1^H 4
                our_images = our_images[:4]

                if self.dev_mode:
                    loginf("%s : number of images %s " % (our_images,
                                                          len(our_images)))

            except Exception as e:
                logerr("image selection failed with %s" % e)
                raise

            # Mastodon posting- Mastodon.media_post
            logdbg("number of images for upload %s" % len(our_images))
            if len(our_images) != 0:
                media_list = []
                for media in range(len(our_images)):
                    if self.dev_mode:
                        loginf("media is %s" % our_images[media])
                    if os.path.isfile(our_images[media]):
                        try:
                            media_id = self.mstdn.media_post(our_images[media])
                            media_list.append(media_id)
                        except Exception as e:
                            raise weewx.restx.FailedPost("mastodon failed: %s" % e)
                    else:
                        pass
                        if self.dev_mode:
                            loginf("media is not a file %s and of type %s" % (
                                   our_images[media], type(our_images[media])))
                if self.dev_mode:
                    loginf("our media_list images are %s : %s" % (media,
                                                                  media_list))
                try:
                    if self.dev_mode:
                        dev_msg += ' : '+self.format_choice+'\n'
                        msg += '\n'+dev_msg
                    self.mstdn.status_post(msg,
                                           media_ids=media_list,
                                           sensitive=False,
                                           visibility=self.visibility
                                           )
                    # ,spoiler_text=msg)
                except Exception as e:
                    raise weewx.restx.FailedPost("media_post failed: %s" % e)
            else:
                try:
                    if self.dev_mode:
                        dev_msg += ' : '+self.format_choice+'\n'
                        msg += '\n'+dev_msg
                    self.mstdn.status_post(msg,
                                           visibility=self.visibility
                                           )
                    return
                except Exception as e:
                    raise weewx.restx.FailedPost("status_post failed: %s" % e)
            return
        else:
            raise weewx.restx.FailedPost("Max retries (%d) exceeded" %
                                         self.max_tries)
