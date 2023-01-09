# since.py
#
# A Search List Extension to provide aggregates since a given hour.
#
# Original author Gary? - it's history, as it is known to me is as follows.
#
# https://groups.google.com/d/msg/weewx-user/VyVMEfuxClo/-ppd0N4bBgAJ
#
"""
 Yes I think Gary wrote a python script to work out 9 am.

 https://github.com/weewx/weewx/files/2082668/since.py.txt

 It is called since.py

 There is a bit in the index.html.tmpl

                      <tr> <td>Today's Rain since 9am</td>
                      <td>$since($hour=9).rain.sum</td> </tr>

 Glenn McKechnie adds...  Further to the above instructions,

 since.py belongs in the user extensions directory  weewx/user/

 it requires " search_list_extensions = user.since.Since " to be inserted under
 the [CheetahGenerator] section in your skin.conf file, as follows...

[CheetahGenerator] # existing section heading - don't duplicate

     search_list_extensions = user.since.Since

If you already have a "search_list_extensions = " stanza then add this to the
end; after a comma. eg:-

     search_list_extensions = user.yourexisting.Entry, user.since.Since


This script was modified around 7th Feb 2022 after it stopped working with
weewx version 4.6.0. An explanation and fix was given by Tom Keffer.
https://groups.google.com/g/weewx-user/c/BKNK5yDo_1w/m/hOQJXXK0DwAJ

# Glenn McKechnie - modified 01/11/22
Modified this (it was still working) after Greg from Oz revisited the above
thread and reminded me of it.  Found gjr80's bin/user/wssearchlist.py
modifications and figure they are probably the original source, or may as well
be.
https://github.com/gjr80/weewx-saratoga/commit/07acc0550ef3c5b44fc2085aa72f52e10a0dae0d
So it's probably fitting that it incoporates those changes, and Tom suggested
there was a better solution.

"""


# python imports
import datetime
import syslog
import time

# weeWX imports
import weewx.cheetahgenerator
import weewx.units
from weewx.tags import TimespanBinder
from weeutil.weeutil import TimeSpan

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
        syslog.syslog(level, 'since: %s' % msg)
    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)
    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)
    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)


VERSION = "0.03"


class Since(weewx.cheetahgenerator.SearchList):
    """SLE to provide aggregates since a given time of day."""

    def __init__(self, generator):
        # call our parent's initialisation
        super(Since, self).__init__(generator)

    def get_extension_list(self, timespan, db_lookup):
        """Returns a NewBinder object that supports aggregates since a given
           time.

            The NewBinder object implements the tag $since that allows
            inclusion of aggregates since the last occurrence of a give time of
            day, eg total rainfall since 9am, average temperature since midday.
            The signature of the $since tag is:

            $since([$hour=x]).obstype.aggregation[.optional_unit_conversion][.optional_formatting]

            where

            x is an integer from 0 to 23 inclusive representing the hour of the
            day

            obstype is a field in the archive table in use eg outTemp,
            inHumidity or rain

            aggregation is an aggregate function supported by weewx (refer
            Customization Guide appendices)

            optional_unit_conversion and optional_formatting are optional weeWX
            unit conversion and formatting codes respectively

        Parameters:
            timespan: An instance of weeutil.weeutil.TimeSpan. This will hold
                      the start and stop times of the domain of valid times.

            db_lookup: This is a function that, given a data binding as its
                       only parameter, will return a database manager object.

        Returns:
            A NewBinder object with a timespan from "hour" o'clock to the
            report time
          """

        t1 = time.time()

        class NewBinder(object):

            def __init__(self, db_lookup, report_time,
                         formatter=None,
                         converter=None,
                         **option_dict):
                """Initialize an instance of WsTimeBinder (NewBinder).
                db_lookup: A function with call signature
                           db_lookup(data_binding), which returns a database
                           manager and where data_binding is an optional
                           binding name. If not given, then a default binding
                           will be used.
                report_time: The time for which the report should be run.
                formatter: An instance of weewx.units.Formatter() holding the
                           formatting information to be used. [Optional. If
                           not given, the default Formatter will be used.]
                converter: An instance of weewx.units.Converter() holding the
                           target unit information to be used. [Optional. If
                           not given, the default Converter will be used.]
                option_dict: Other options which can be used to customize
                             calculations. [Optional.]
                """
                self.db_lookup = db_lookup
                self.report_time = report_time
                self.formatter = formatter or weewx.units.Formatter()
                self.converter = converter or weewx.units.Converter()
                self.option_dict = option_dict

            def since(self, data_binding=None, hour=0, minute=0):
                """Return a TimeSpanBinder for the period since 'hour'."""
                # obtain the report time as a datetime object
                stop_dt = datetime.datetime.fromtimestamp(timespan.stop)
                # assume the 'since' time is today so obtain it as a datetime
                # object
                since_dt = stop_dt.replace(hour=hour, minute=minute)
                # but 'since' must be before the report time so check if the
                # assumption is correct, if not then 'since' must be yesterday
                # so subtract 1 day
                if since_dt > stop_dt:
                    since_dt -= datetime.timedelta(days=1)
                # now convert it to unix epoch time:
                since_ts = time.mktime(since_dt.timetuple())
                # get our timespan
                since_tspan = TimeSpan(since_ts, timespan.stop)
                # now return a TimespanBinder object, using the timespan we
                # just calculated
                return TimespanBinder(since_tspan,
                                      self.db_lookup, context='current',
                                      data_binding=data_binding,
                                      formatter=self.formatter,
                                      converter=self.converter,
                                      **self.option_dict)

        time_binder = NewBinder(db_lookup,
                                timespan.stop,
                                self.generator.formatter,
                                self.generator.converter)

        t2 = time.time()
        logdbg("Since SLE executed in %0.3f seconds" % (t2-t1))

        return [time_binder]
