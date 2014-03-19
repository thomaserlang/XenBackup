"""
https://github.com/morganfainberg/python-rfc5424-logging-formatter

Copyright (C) 2013 Morgan Fainberg and Metacloud, Inc

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging
import time
import socket
import datetime
import re


class RFC5424Formatter(logging.Formatter):
    '''
    A derived formatter than allows for isotime specification
    for full RFC5424 compliancy (with corrected TZ format)

    For a "proper" ISOTIME format, use "%(isotime)s" in a
    formatter instance of this class or a class derived from
    this class.  This is for a work-around where strftime
    has no mechanism to produce timezone in the format of
    "-08:00" as required by RFC5424.

    The '%(isotime)s' replacement will read in the record
    timestamp and try and reparse it.  This really is a
    problem with RFC5424 and strftime.  I am unsure if this
    will be fixed in the future (in one or the other case)

    This formatter has an added benefit of allowing for
    '%(hostname)s' to be specified which will return a '-'
    as specified in RFC5424 if socket.gethostname() returns
    bad data (exception).

    The RFC5424 format string should look somthing like:

    %(isotime)s %(hostname)s %(name)s %(process)d - - %(message)s

    The section after the two "- -" is technically the message
    section, and can have any data applied to it e.g.:

        <...> %(levelname)s [%(module)s %(funcName)s] %(message)s

    The '- -' section is the "msg ID" and "Structured-Data" Elements,
    respectively

    MSGID (Description from RFC5424):
       The MSGID SHOULD identify the type of message.  For example, a
   firewall might use the MSGID "TCPIN" for incoming TCP traffic and the
   MSGID "TCPOUT" for outgoing TCP traffic.  Messages with the same
   MSGID should reflect events of the same semantics.  The MSGID itself
   is a string without further semantics.  It is intended for filtering
   messages on a relay or collector.
   The NILVALUE SHOULD be used when the syslog application does not, or
   cannot, provide any value.

   Stuctured Data Example:
        [exampleSDID@32473 iut="3" eventSource="Application" eventID="1011"]
    '''
    def __init__(self, *args, **kwargs):
        self._tz_fix = re.compile(r'([+-]\d{2})(\d{2})$')
        super(RFC5424Formatter, self).__init__(*args, **kwargs)

    def format(self, record):
        try:
            record.__dict__['hostname'] = socket.gethostname()
        except:
            record.__dict__['hostname'] = '-'
        isotime = datetime.datetime.fromtimestamp(record.created).isoformat()
        tz = self._tz_fix.match(time.strftime('%z'))
        if time.timezone and tz:
            (offset_hrs, offset_min) = tz.groups()
            isotime = '{0}{1}:{2}'.format(isotime, offset_hrs, offset_min)
        else:
            isotime = isotime + 'Z'

        record.__dict__['isotime'] = isotime

        return super(RFC5424Formatter, self).format(record)