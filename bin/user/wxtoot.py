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
        access_token = "Your access token"
        mastodon_url = "The mastodon url"

toots look something like this:

STATION_IDENTIFIER: Ws: 0.0; Wd: -; Wg: 1.1; oT: 7.00;
                    oH: 97.00; P: 1025.307; R: 0.000

The STATION_IDENTIFIER is the first part of the station 'location' defined in
weewx.conf.  To specify a different identifier for tweets, use the 'station'
parameter.  For example:

[StdRESTful]
    [[Mastodon]]
        station = hal

The 'format' parameter determines the tweet contents.  The default format is:

format = {station:%.8s}: Ws: {windSpeed:%.1f}; Wd: {windDir:%03.0f};
         Wg: {windGust:%.1f}; oT: {outTemp:%.1f}; oH: {outHumidity:%.2f};
         P: {barometer:%.3f}; R: {rain:%.3f}

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

By default, the units are those specified by the unit system in the
StdConvert section of weewx.conf.  To specify a different unit system,
use the unit_system option:

[StdRESTful]
    [[Mastodon]]
        unit_system = METRICWX

Possible values include US, METRIC, or METRICWX.
"""

try:
    # Python 3
    import queue
except ImportError:
    # Python 2
    import Queue as queue
import re
import sys
import time
import weewx
import weewx.restx
import weewx.units
from weeutil.weeutil import to_bool
import requests
import shutil
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
        syslog.syslog(level, 'Mastodon: %s' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)

    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)

    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)


VERSION = "0.02"

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


class Rastodon(weewx.restx.StdRESTbase):

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

    _DEFAULT_FORMAT_3 = '{station:%.8s}: Ws: {windSpeed:%.1f}; Wd:'

    _DEFAULT_FORMAT_NONE = '-'
    _DEFAULT_ORDINALS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S',
                         'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW', 'N', '-']

    def __init__(self, engine, config_dict):
        """This service recognizes standard restful options plus the following:

        Required parameters:

        mastodon authentication credentials:
        access_token
        mastodon_url

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
        super(Rastodon, self).__init__(engine, config_dict)
        loginf('service version is %s' % VERSION)

        site_dict = weewx.restx.get_site_dict(config_dict,
                                              'Mastodon',
                                              'access_token',
                                              'post_interval',
                                              'cardinal',
                                              'format_choice',
                                              'mastodon_url')
        if site_dict is None:
            logerr("site_dict failed, is it complete? : %s" % site_dict)
            return
        loginf("site_dict = %s" % site_dict)

        # development only
        # visibility : options are ... public, unlisted, private, direct
        site_dict.setdefault('visibility', 'direct')

        # default the station name
        site_dict.setdefault('station', engine.stn_info.location)

        # if a unit system was specified, get the weewx constant for it.
        # do it here so a bogus unit system will cause weewx to die
        # immediately, not simply cause the mastodon thread to crap out.
        usn = site_dict.get('unit_system')
        if usn is not None:
            site_dict['unit_system'] = weewx.units.unit_constants[usn]
            loginf('units will be converted to %s' % usn)

        site_dict.setdefault('format_ordinal', False)
        site_dict['format_ordinal'] = to_bool(site_dict.get('cardinal'))
        # if site_dict['cardinal']:
        #    site_dict.setdefault['format_ordinal'] = 'ord'
        if site_dict['format_choice'] == 'simple':
            site_dict.setdefault('format', self._DEFAULT_FORMAT_1)
        elif site_dict['format_choice'] == 'full':
            site_dict.setdefault('format', self._DEFAULT_FORMAT_2)
        elif site_dict['format_choice'] == 'template':
            site_dict.setdefault('format', self._DEFAULT_FORMAT_3)
        else:
            site_dict.setdefault('format', self._DEFAULT_FORMAT_3)

        site_dict.setdefault('format_None', self._DEFAULT_FORMAT_NONE)
        site_dict.setdefault('format_utc', False)
        site_dict['format_utc'] = to_bool(site_dict.get('format_utc'))
        site_dict.setdefault('ordinals', self._DEFAULT_ORDINALS)
        # loginf("visibility = %s" % self.visibility)

        # we can bind to archive or loop events, default to archive
        binding = site_dict.pop('binding', 'archive')
        if isinstance(binding, list):
            binding = ','.join(binding)
        loginf('binding is %s' % binding)

        self.data_queue = queue.Queue()
        data_thread = MastodonThread(self.data_queue, **site_dict)
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


class MastodonThread(weewx.restx.RESTThread):
    def __init__(self, queue,
                 access_token, mastodon_url, visibility, cardinal,
                 format_choice, station, format, format_None,
                 ordinals, format_utc=True, format_ordinal=True,
                 unit_system=None, skip_upload=False,
                 log_success=True, log_failure=True,
                 post_interval=None, max_backlog=sys.maxsize, stale=None,
                 timeout=60, max_tries=3, retry_wait=5):
        super(MastodonThread, self).__init__(queue,
                                             protocol_name='Mastodon',
                                             manager_dict=None,
                                             post_interval='3600',
                                             max_backlog=max_backlog,
                                             stale=stale,
                                             log_success=log_success,
                                             log_failure=log_failure,
                                             max_tries=max_tries,
                                             timeout=timeout,
                                             retry_wait=retry_wait)

        self.mstdn = Mastodon(access_token=access_token,
                              api_base_url=mastodon_url)

        # Mastodon Information
        self.masturl_media = mastodon_url + "/api/v2/media"
        # self.masturl_status = mastodon_url + "/api/v1/statuses"
        self.mastodon_auth = {'Authorization': 'Bearer ' + access_token}
        self.access_token = access_token
        self.mastodon_url = 'https://mastodon.au/'
        self.station = station
        self.format = format
        self.format_None = format_None
        self.visibility = visibility
        self.ordinals = ordinals
        self.format_utc = format_utc
        self.format_ordinal = format_ordinal
        self.unit_system = unit_system
        self.skip_upload = to_bool(skip_upload)

        # self.access_token = access_token
        self.mstdn = Mastodon(access_token=self.access_token,
                              api_base_url=self.mastodon_url)

        if self.format_ordinal:
            self.cardinal = 'ord'
        else:
            self.cardinal = 'deg'

    def format_toot(self, record):
        msg = self.format
        for obs in record:
            oldstr = None
            fmt = '%s'
            pattern = "{%s}" % obs
            m = re.search(pattern, msg)
            if m:
                oldstr = m.group(0)
            else:
                pattern = "{%s:([^}]+)}" % obs
                m = re.search(pattern, msg)
                if m:
                    oldstr = m.group(0)
                    fmt = m.group(1)
            # loginf("obs = %s" % obs)
            if oldstr is not None:
                if obs == 'dateTime':
                    if self.format_utc:
                        ts = time.gmtime(record[obs])
                    else:
                        ts = time.localtime(record[obs])
                    newstr = time.strftime(fmt, ts)
                elif record[obs] is None:
                    newstr = self.format_None
                elif obs == 'windDir' and self.cardinal == 'ord':
                    newstr = (_dir_to_ord(record[obs], self.ordinals))
                else:
                    newstr = fmt % record[obs]
                msg = msg.replace(oldstr, newstr)
        logdbg('msg: %s' % msg)
        # loginf('info msg: %s' % msg)
        return msg

    def process_record(self, record, dummy_manager):
        if self.unit_system is not None:
            record = weewx.units.to_std_system(record, self.unit_system)
        record['station'] = self.station

        msg = self.format_toot(record)
        if self.skip_upload:
            loginf('skipping upload')
            return

        # now do the posting
        ntries = 0
        while ntries < self.max_tries:
            ntries += 1
            try:
                #loginf("Mastodon NOT running")
                #return
                pass
            except Exception as e:
                logerr("1st except is %s" % e)

            # collect images / media
            try:
                # fetch from web server
                image = requests.get('http://127.0.0.1/weewx/wxgraphic/index.php', stream = True)
                if image.status_code == 200:
                     # Set decode_content value to True, otherwise the downloaded image file's size will be zero.
                     image.raw.decode_content = True

                img = '/tmp/wxgraphic.png'
                with open(img,'wb') as f:
                    shutil.copyfileobj(image.raw, f)
                loginf("Local image output as %s " % image)

                # fetch from local file system
                img_1 = '/tmp/daytempdew.png'
                img_2 = '/var/www/html/weewx/dayrain.png'
                img_3 = '/var/www/html/weewx/daywind.png'

                # maybe a list to loop thru?
                images = (img, img_1, img_2, img_3)
            except Exception as e:
                logerr("2nd except is %s" % e)
                # raise weewx.restx.FailedPost("Local image fetch failed: %s" % e)

            # Mastodon.media_post

            media_id0 = self.mstdn.media_post(img)
            media_id1 = self.mstdn.media_post(img_1)
            media_id2 = self.mstdn.media_post(img_2)
            media_id3 = self.mstdn.media_post(img_3)
            logdbg("media posted as %s & %s & %s & %s" % (media_id0,
                                                          media_id1,
                                                          media_id2,
                                                          media_id3))
            try:
                # _msg = ''
                self.mstdn.status_post(msg,
                                       media_ids=(media_id0, media_id1,
                                       media_id2, media_id3),
                                       sensitive=False)
                                       # ,spoiler_text=msg)
            except Exception as e:
                logerr("3rd except is %s" % e)
                #raise weewx.restx.FailedPost("media_id failed: %s" % e)

            try:
                self.mstdn.status_post(msg)  # ,
                                      # spoiler_text='test_upload')
                                      # media_ids=media_id,

                #logdbg("mastodon as %s" % msg)  # debug only

                return
            except Exception as e:
                logerr("4th except is %s" % e)
                #raise weewx.restx.FailedPost("Authorization mstdn failed: %s" % e)
        else:
            raise weewx.restx.FailedPost("Max retries (%d) exceeded" %
                                         self.max_tries)
