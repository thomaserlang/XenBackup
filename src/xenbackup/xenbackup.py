"""
The MIT License (MIT)

Copyright (c) 2014 Thomas Erlang Sloth

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import XenAPI
import time
import urllib2
import base64
import socket
import os.path
import os
import argparse
import logging
import inspect
from rfc5424 import RFC5424Formatter
from datetime import datetime
from logging.handlers import SysLogHandler

logger = logging.getLogger('xenbackup_logger')

class XenBackup(object):

    def __init__(self, server, user, password):
        '''
        :param server: str
        :param user: str
        :param password: str
        '''
        self.session = XenAPI.Session('https://{}'.format(server))
        self.session.xenapi.login_with_password(user, password)
        self.server = server
        self.auth = auth = base64.encodestring("%s:%s" % (user, password)).strip()

    def get_vms(self):
        all_vms = self.session.xenapi.VM.get_all_records()
        vms = {}
        for vm in all_vms:
            vm_record = all_vms[vm]
            if vm_record['is_a_template']:
                continue
            if vm_record['is_control_domain']:
                continue
            vms[vm] = vm_record
        return vms

    def create_snapshot(self, opaque_ref, vm_info, retry_max=3, retry_delay=30):
        '''
        :param opaque_ref: str
            OpaqueRef of the VM to create a snapshot from
        :param vm_info: dict
            Retrieved from get_vms()
        :param retry_max: int
            Maximum number of retries
        :param retry_delay: int
            wait x number of seconds before retrying
        :returns: tuple (snapshot_opaque_ref, name)
            returns the opaque_ref id and the name of the snapshot
        '''
        logging.info('[{}][{}] Creating snapshot'.format(self.server, vm_info['name_label']))
        done = False
        tries = 0
        while not done and tries <= retry_max:
            if tries and (retry_max >= tries):
                logging.notice('[{}][{}] Retrying snapshot creation in {} seconds [{}/{}]'.format(self.server, vm_info['name_label'], retry_delay, tries, retry_max))
                time.sleep(retry_delay)
            try:
                tries += 1
                name = '{}-{}'.format(vm_info['name_label'], datetime.utcnow().strftime('%Y%m%dT%H%M%SZ'))
                result = self.session.xenapi.VM.snapshot(opaque_ref, name)
                logging.info('[{}][{}] Snapshot "{}" successfully created'.format(self.server, vm_info['name_label'], name))
                return (result, name)
                done = True
            except Exception, e:
                logging.error('[{}][{}] Error creating snapshot: {}'.format(self.server, vm_info['name_label'], str(e)))

    def download_snapshot(self, opaque_ref, vm_info, path, retry_max=3, retry_delay=30):
        '''
        :param opaque_ref: str
            OpaqueRef of the VM to create a snapshot from
        :param vm_info: dict
            Retrieved from get_vms()
        :param retry_max: int
            Maximum number of retries
        :param retry_delay: int
            wait x number of seconds before retrying.
        '''
        snapshot_opaque_ref, snapshot_name = self.create_snapshot(opaque_ref, vm_info, retry_max, retry_delay)
        if not snapshot_opaque_ref:
            return None
        logger.info('[{}][{}] Downloading snapshot: {}'.format(self.server, vm_info['name_label'], snapshot_name))
        done = False
        tries = 0
        while not done and tries <= retry_max:
            if tries and (retry_max >= tries):                
                logger.notice('[{}][{}] Retrying snapshot downloading in {} seconds [{}/{}]'.format(self.server, vm_info['name_label'], retry_delay, tries, retry_max))
                time.sleep(retry_delay)
            try:
                tries += 1
                url = 'https://{}/export?uuid={}'.format(self.server, self.session.xenapi.VM.get_uuid(snapshot_opaque_ref))
                path = os.path.abspath(os.path.join(path, vm_info['name_label']))
                if not os.path.exists(path):
                    os.mkdir(path)
                path = os.path.abspath(os.path.join(path, '{}.xva'.format(snapshot_name)))
                self._download_url(path, url)
                logger.info('[{}][{}] Snapshot "{}" successfully downloaded. Removing snapshot from the server'.format(self.server, vm_info['name_label'], snapshot_name))
                self.session.xenapi.VM.destroy(snapshot_opaque_ref)
                done = True
            except Exception, e:
                logger.error('[{}][{}] Error downloading snapshot: {}'.format(self.server, vm_info['name_label'], str(e)))

    def _download_url(self, path, url):
        socket.setdefaulttimeout(120)
        request = urllib2.Request(url)
        request.add_header('Authorization', 'Basic {}'.format(self.auth))
        result = urllib2.urlopen(request)
        with open(path, r'wb') as f:
            block_sz = 8192
            while True:
                buffer = result.read(block_sz)
                if not buffer:
                    break
                f.write(buffer)

    def rotate(self, path, snapshots_max=3):
        '''
        :param path: str
        :param snapshots_max: int - default 3
        :returns: boolean
        '''
        try:
            dirs = os.listdir(path)
            for vm in dirs:
                path = os.path.abspath(os.path.join(path, vm))
                if not os.path.isdir(path):
                    continue
                files = os.listdir(path)
                count = len(files)
                if count > snapshots_max:
                    for snapshot in files[0:count-snapshots_max]:
                        os.remove(os.path.abspath(os.path.join(path, snapshot)))
            return True
        except Exception, e:
            logger.error('[{}] Error rotating snapshots: {}'.format(self.server, str(e)))
            return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', help='backup directory', required=True, type=str)
    parser.add_argument('--host', help='xenserver host', required=True, type=str)
    parser.add_argument('--user', help='xenserver user', required=True, type=str)
    parser.add_argument('--password', help='xenserver password', required=True, type=str)

    parser.add_argument('--retry_max', help='max retries per VM', default=3, type=int)    
    parser.add_argument('--retry_delay', help='number of seconds to wait after each failed try', default=30, type=int)

    parser.add_argument('--rotate_snapshots', help='enable rotate', default=True, type=bool)
    parser.add_argument('--rotate_snapshots_max', help='maximum number of snapshots stored in a directory', default=3, type=int)

    parser.add_argument('--vms', help='a comma separated list of virtual machines to backup', default='', type=str)

    parser.add_argument('--syslog_ip', help='ip/hostname of the syslog server', default='127.0.0.1', type=str)
    parser.add_argument('--syslog_port', help='port of the syslog server', default=514, type=int)

    args = parser.parse_args()

    logger = logging.getLogger('xenbackup')
    handler = SysLogHandler(
        address=(args.syslog_ip, args.syslog_port),
        facility=14,
    )
    handler.setFormatter(
        RFC5424Formatter(
            '1 %(isotime)s %(hostname)s %(name)s %(process)d - - %(message)s'
        )
    )
    logger.addHandler(handler)
    logger.setLevel(20)
    logger.info('[{}] Starting backup of VMs'.format(args.host))
    try:
        xenbackup = XenBackup(
            server=args.host,
            user=args.user,
            password=args.password,
        )
        backup_vms = args.vms.lower().split(',')
        vms = xenbackup.get_vms()
        for vm in vms:
            if (vms[vm]['name_label'].lower() in backup_vms) or not backup_vms:
                xenbackup.download_snapshot(
                    opaque_ref=vm,
                    vm_info=vms[vm],
                    path=args.path,
                    retry_max=args.retry_max,
                    retry_delay=args.retry_delay,
                )

        if args.rotate_snapshots:
            xenbackup.rotate(
                path=args.path,
                snapshots_max=args.rotate_snapshots_max,
            )
    except Exception, e:
        logger.error('[{}] Error occurred when trying to backup VMS. {}'.format(args.host, str(e)))
        raise