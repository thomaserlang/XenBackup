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
import json
from rfc5424 import RFC5424Formatter
from datetime import datetime
from logging.handlers import SysLogHandler

logger = logging.getLogger('xenbackup_logger')

class XenBackup(object):

    def __init__(self, server, user, password, logger=None):
        '''
        :param server: str
        :param user: str
        :param password: str
        '''
        self.session = XenAPI.Session('https://{}'.format(server))
        self.session.xenapi.login_with_password(user, password)
        self.server = server
        self.auth = auth = base64.encodestring("%s:%s" % (user, password)).strip()
        self.logger = logger

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
        vm_uuid = self.session.xenapi.VM.get_uuid(opaque_ref)
        self.logger.info('Creating snapshot [xenserver="{}"] [vm_name="{}"] [uuid="{}"]'.format(
            self.server, 
            vm_info['name_label'],
            vm_uuid,
        ))
        done = False
        tries = 0
        while not done and tries <= retry_max:
            if tries and (retry_max >= tries):
                self.logger.notice('Retrying snapshot creation in {} seconds [{}/{}][uuid="{}"]'.format(
                    retry_delay, 
                    tries, 
                    retry_max, 
                    self.server, 
                    vm_info['name_label'], 
                    vm_uuid,
                ))
                time.sleep(retry_delay)
            try:
                tries += 1
                name = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
                result = self.session.xenapi.VM.snapshot(opaque_ref, name)
                self.logger.info('Snapshot [snapshot_name="{}"] successfully created [xenserver="{}"] [vm_name="{}"] [uuid="{}"]'.format(
                    name, 
                    self.server, 
                    vm_info['name_label'], 
                    vm_uuid,
                ))
                return (result, name)
                done = True
            except Exception, e:
                self.logger.error('Error creating snapshot: {} [xenserver="{}"] [vm_name="{}"] [uuid="{}"]'.format(
                    str(e),
                    self.server, 
                    vm_info['name_label'], 
                    vm_uuid
                ))

    def download_vm(self, opaque_ref, vm_info, path, retry_max=3, retry_delay=30):
        '''
        :param opaque_ref: str
            OpaqueRef of the VM to create a snapshot from
        :param vm_info: dict
            Retrieved from get_vms()
        :param retry_max: int
            Maximum number of retries
        :param retry_delay: int
            wait x number of seconds before retrying.
        :returns: boolean
        '''
        snapshot_opaque_ref, snapshot_name = self.create_snapshot(opaque_ref, vm_info, retry_max, retry_delay)
        if not snapshot_opaque_ref:
            return None
        vm_uuid = self.session.xenapi.VM.get_uuid(opaque_ref)
        self.logger.info('Downloading vm to file: {}.xva [xenserver="{}"] [vm_name="{}"] [uuid="{}"]'.format(
            snapshot_name, 
            self.server, 
            vm_info['name_label'],
            vm_uuid,
        ))
        done = False
        tries = 0
        while not done and tries <= retry_max:
            if tries and (retry_max >= tries):                
                self.logger.notice('Retrying download of snapshot in {} seconds [{}/{}] [xenserver="{}"] [vm_name="{}"] [uuid="{}"]'.format(
                    retry_delay, 
                    ries, 
                    retry_max,
                    self.server, 
                    vm_info['name_label'], 
                    vm_uuid,
                ))
                time.sleep(retry_delay)
            try:
                tries += 1
                url = 'https://{}/export?uuid={}'.format(self.server, self.session.xenapi.VM.get_uuid(snapshot_opaque_ref))
                vm_path = os.path.abspath(os.path.join(path, vm_uuid))
                if not os.path.exists(vm_path):
                    os.mkdir(vm_path)
                    with open(os.path.join(path, 'vms_lookup.json'), 'w+') as f:
                        try:
                            data = json.load(f)
                        except ValueError:
                            data = {}
                        data[vm_uuid] = {
                            'name': vm_info['name_label'],
                        }
                        json.dump(
                            data,
                            f,
                            sort_keys=True,
                            indent=4, 
                            separators=(',', ': '),
                        )
                vm_snap_path = os.path.abspath(os.path.join(vm_path, '{}.xva'.format(snapshot_name)))
                self._download_url(vm_snap_path, url)
                self.logger.info('Snapshot "{}" successfully downloaded. Removing snapshot from the server [xenserver="{}"] [vm_name="{}"] [uuid="{}"]'.format(
                    snapshot_name,
                    self.server, 
                    vm_info['name_label'], 
                    vm_uuid,
                ))
                self.session.xenapi.VM.destroy(snapshot_opaque_ref)
                done = True
                return True
            except Exception, e:
                self.logger.error('Error downloading snapshot: {} [xenserver="{}"] [vm_name="{}"]'.format(
                    str(e),
                    self.server, 
                    vm_info['name_label'], 
                ))
        return False

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
            self.logger.error('Error rotating snapshots: {} [xenserver="{}"]'.format(str(e), self.server))
        return False
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', help='backup directory', required=True, type=str)
    parser.add_argument('--host', help='xenserver host', required=True, type=str)
    parser.add_argument('--user', help='xenserver user', required=True, type=str)
    parser.add_argument('--password', help='xenserver password', required=True, type=str)

    parser.add_argument('--retry_max', help='max retries per VM', default=3, type=int)    
    parser.add_argument('--retry_delay', help='number of seconds to wait after each failed try', default=30, type=int)

    parser.add_argument('--rotate_snapshots', help='enable rotate', default=True, type=bool)
    parser.add_argument('--rotate_snapshots_max', help='maximum number of snapshots stored in a directory', default=3, type=int)

    parser.add_argument('--vms', help='a comma separated list of virtual machines to backup', default=None, type=str)

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
    logger.info('Starting backup of VMs [xenserver="{}"] '.format(args.host))
    try:
        xenbackup = XenBackup(
            server=args.host,
            user=args.user,
            password=args.password,
            logger=logger,
        )
        backup_vms = []
        if args.vms:
            backup_vms = args.vms.lower().split(',')
        vms = xenbackup.get_vms()
        for vm in vms:
            if (vms[vm]['name_label'].lower() in backup_vms) or not backup_vms:
                xenbackup.download_vm(
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
        logger.error('Error occurred when trying to backup VMS. {} [xenserver="{}"]'.format(
            str(e), 
            args.host
        ))
        raise

if __name__ == '__main__':
    main()