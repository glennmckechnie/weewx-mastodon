"""weewx module to tweet weather data

Prerequisites

This module requires the twython twitter api in python.

pip install twython

Installation

Put this file in the bin/user directory.

Configuration

Add the following to weewx.conf:

[Twitter]
    app_key = APP_KEY
    app_secret = APP_SECRET
    oauth_token = OAUTH_TOKEN
    oauth_token_secret = OAUTH_TOKEN_SECRET

[Engines]
    [[WxEngine]]
        process_services = ... , user.twitter.Twitter
"""

import syslog
import time
from twython import Twython, TwythonError, TwythonAuthError, TwythonRateLimitError
import weewx
from weewx.wxengine import StdService

VERSION = "0.1"

def logmsg(level, msg):
    syslog.syslog(level, 'twitter: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

class Twitter(StdService):
    def __init__(self, engine, config_dict):
        super(Twitter, self).__init__(engine, config_dict)
        d = config_dict.get('Twitter', {})
        self.app_key = d['app_key']
        self.app_secret = d['app_secret']
        self.oauth_token = d['oauth_token']
        self.oauth_token_secret = d['oauth_token_secret']
        self.max_tries = int(d.get('max_tries', 3))
        self.bind(weewx.NEW_LOOP_PACKET, self.tweetLoopPacket)
        #self.bind(weewx.NEW_ARCHIVE_PACKET, self.tweetArchiveRecord)

    def tweetLoopPacket(self, event):
        self.sendTweet(event.packet)

    def tweetArchiveRecord(self, event):
        self.sendTweet(event.record)

    def sendTweet(self, packet):
        wstr = "ts: %s; P: %s; iT: %s; oT: %s; iH: %s; oH: %s; Ws: %s; Wg: %s; Wd: %s; R: %s" % (
            packet['dateTime'],
            packet['barometer'],
            packet['inTemp'], packet['outTemp'],
            packet['inHumidity'], packet['outHumidity'],
            packet['windSpeed'], packet['windGust'], packet['windDir'],
            packet['rain'])
        ntries = 0
        while ntries < self.max_tries:
            ntries += 1
            twitter = Twython(self.app_key, self.app_secret,
                              self.oauth_token, self.oauth_token_secret)
            twitter.update_status(status=wstr)
            except (TwythonError, TwythonAuthError, TwythonRateLimitError), e:
                logerr("Failed attempt %d of %d to tweet: %s" %
                       (ntries, self.max_tries, e))
                logdbg("Waiting %d seconds before retry" % self.retry_wait)
                time.sleep(self.retry_wait)
        else:
            msg = "Max retries (%d) exceeded for tweeting" % self.max_tries
            logerr(msg)
