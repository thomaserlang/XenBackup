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
import ssl
import argparse
import logging
import json
import logstash
from archive_rotator import rotator
from archive_rotator.algorithms import SimpleRotator
from datetime import datetime
from logging.handlers import SysLogHandler

class XenBackup(object):

    def __init__(self, server, user, password, rotate=True, rotate_num=5, logger=None):
        '''
        :param server: str
        :param user: str
        :param password: str
        '''
        self.auth = auth = base64.encodestring("%s:%s" % (user, password)).strip()
        self.logger = logger
        self.enable_rotate = rotate
        self.rotate_num = rotate_num
        self.server = self.login(server, user, password)

    def login(self, server, user, password):
        try:
            self.session = XenAPI.Session('https://{}'.format(server))
            self.session.xenapi.login_with_password(user, password)
            return server
        except XenAPI.Failure as e:
            if e.details[0] == 'HOST_IS_SLAVE':
                newserver = e.details[1]
                self.logger.info('{} is a slave, changing to the master: {}'.format(
                    server,
                    newserver,
                ))
                return self.login(newserver, user, password) 
            raise

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
        extra = {
            'host': self.server,
            'vm_name': vm_info['name_label'],
            'vm_uuid': vm_uuid, 
        }
        self.logger.info('Creating snapshot from {}'.format(
            vm_info['name_label'],
        ), extra)
        done = False
        tries = 0
        while not done and tries <= retry_max:
            if tries and (retry_max >= tries):
                self.logger.info('Retrying snapshot creation in {} seconds [{}/{}]'.format(
                    retry_delay, 
                    tries, 
                    retry_max, 
                ), extra=extra)
                time.sleep(retry_delay)
            try:
                tries += 1
                name = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
                result = self.session.xenapi.VM.snapshot(opaque_ref, '{}_{}'.format(vm_info['name_label'], name))
                self.logger.info('Snapshot successfully created from {}'.format(
                    vm_info['name_label'],
                ), extra=extra)
                return result
                done = True
            except Exception, e:
                self.logger.error('Error creating snapshot on {}'.format(
                    vm_info['name_label'],
                ), extra=extra)

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
        snapshot_opaque_ref = self.create_snapshot(opaque_ref, vm_info, retry_max, retry_delay)
        if not snapshot_opaque_ref:
            return None
        vm_uuid = self.session.xenapi.VM.get_uuid(opaque_ref)
        extra = {
            'host': self.server,
            'vm_name': vm_info['name_label'],
            'vm_uuid': vm_uuid, 
        }
        filename = '{}-{}.xva'.format(vm_info['name_label'], vm_uuid)
        folder = '{}'.format(vm_info['name_label'])
        self.logger.info('Downloading vm snapshot from {}'.format(
            vm_info['name_label']
        ), extra=extra)
        done = False
        tries = 0
        while not done and tries <= retry_max:
            if tries and (retry_max >= tries):                
                self.logger.info('Retrying download of snapshot in {} seconds [{}/{}]'.format(
                    retry_delay, 
                    tries, 
                    retry_max,
                ), extra=extra)
                time.sleep(retry_delay)
            try:
                tries += 1
                url = 'https://{}/export?uuid={}'.format(self.server, self.session.xenapi.VM.get_uuid(snapshot_opaque_ref))
                vm_path = os.path.abspath(os.path.join(path, folder))
                if not os.path.exists(vm_path):
                    os.mkdir(vm_path)    
                vm_snap_path = os.path.abspath(os.path.join(vm_path, filename))
                self._download_url(vm_snap_path, url)
                self.logger.info('Snapshot for vm {} successfully downloaded. Removing snapshot from the server.'.format(
                    vm_info['name_label'],
                ), extra=extra)                
                self.delete_snapshot(snapshot_opaque_ref, vm_info)
                if self.enable_rotate:
                    self.rotate(vm_snap_path)
                done = True
                return True
            except Exception, e:
                self.logger.exception('Error downloading snapshot for {}'.format(
                    vm_info['name_label'], 
                ), extra={
                    'error': str(e),
                    'host': self.server,
                    'vm_name': vm_info['name_label'],
                })
        return False

    def delete_snapshot(self, snapshot_opaque_ref, vm_info):
        try:
            snap_record = self.session.xenapi.VM.get_record(snapshot_opaque_ref)  
            for vbd in snap_record['VBDs']:
                vbd_record = self.session.xenapi.VBD.get_record(vbd)
                if vbd_record['type'].lower() != 'disk':
                    continue                
                vdi = vbd_record['VDI']
                sr = self.session.xenapi.VDI.get_SR(vdi)
                self.session.xenapi.VDI.destroy(vdi)
            self.session.xenapi.VM.destroy(snapshot_opaque_ref)
            return True
        except Exception, e:
            self.logger.exception('Error deleting snapshot for {}'.format(vm_info['name_label']), extra={
                'error': str(e),
                'host': self.server,
                'vm_name': vm_info['name_label'],
            })
        return False

    def _download_url(self, path, url):
        socket.setdefaulttimeout(120)
        request = urllib2.Request(url)
        request.add_header('Authorization', 'Basic {}'.format(self.auth))
        result = urllib2.urlopen(request, context=ssl._create_unverified_context())
        with open(path, r'wb') as f:
            block_sz = 8192
            while True:
                buffer = result.read(block_sz)
                if not buffer:
                    break
                f.write(buffer)

    def rotate(self, path):
        '''
        :param path: str
        :returns: boolean
        '''
        try:
            rotator.rotate(
                SimpleRotator(self.rotate_num, False),
                path=path,
                ext='.xva',
            )
            return True
        except Exception, e:
            self.logger.error('Error rotating snapshots', extra={
                'host': self.server,
                'error': str(e),
            })
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', help='backup directory', required=True, type=str)
    parser.add_argument('--host', help='xenserver host', required=True, type=str)
    parser.add_argument('--user', help='xenserver user', required=True, type=str)
    parser.add_argument('--password', help='xenserver password', required=True, type=str)

    parser.add_argument('--retry_max', help='max retries per VM', default=3, type=int)    
    parser.add_argument('--retry_delay', help='number of seconds to wait after each failed try', default=30, type=int)

    parser.add_argument('--rotate', help='enable rotate', default=True, type=bool)
    parser.add_argument('--rotate_num', help='maximum number of snapshots stored in a directory', default=5, type=int)

    parser.add_argument('--vms', help='a comma separated list of virtual machines to backup', default=None, type=str)

    parser.add_argument('--logstash_host', help='ip/hostname of the syslog server', default='127.0.0.1', type=str)
    parser.add_argument('--logstash_port', help='port of the syslog server', default=5959, type=int)

    args = parser.parse_args()

    logger = logging.getLogger('xenbackup')
    logger.addHandler(logging.StreamHandler())
    logger.addHandler(logstash.LogstashHandler(args.logstash_host, args.logstash_port, version=1))
    logger.setLevel(logging.INFO)
    logger.info('Starting backup of VMs on {} '.format(args.host), extra={
        'host': args.host,
    })
    try:
        xenbackup = XenBackup(
            server=args.host,
            user=args.user,
            password=args.password,
            logger=logger,
            rotate=args.rotate,
            rotate_num=args.rotate_num,
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
    except Exception, e:
        logger.exception('Error occurred when trying to backup VMS from {}'.format(
            args.host
        ))
        raise

if __name__ == '__main__':
    main()