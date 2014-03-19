XenBackup
=========
Backup virtual machines from a XenServer. Tested with Python 2.7.

Example:

    xenbackup.py --host xenserver1 --user root --password pw --path=/var/xenbackup

# Arguments

```
  -h, --help            show this help message and exit

  --path PATH           backup directory (Required)
                        will be stored as path/<vm-name>/<vm-name>-<iso8601-timestamp>.xva

  --host HOST           xenserver host (Required)

  --user USER           xenserver user (Required)

  --password PASSWORD   xenserver password (Required)

  --retry_max RETRY_MAX max retries per VM (default 3)

  --retry_delay RETRY_DELAY (default 30 seconds)
                        number of seconds to wait after each failed try

  --rotate_snapshots ROTATE_SNAPSHOTS (default True)
                        enable rotate

  --rotate_snapshots_max ROTATE_SNAPSHOTS_MAX (default 3)
                        maximum number of snapshots stored in a directory

  --vms vm1,vm2         a comma separated list of virtual machines to backup,
                        will backup all virtual machines by default.

  --syslog_ip IP        (default 127.0.0.1)

  --syslog_port PORT    (default 514)

```

# How it works

 1. Retrives all the virtual machines running on the XenServer
 2. Creates a snapshot
 3. Downloads the snapshot
 4. Deletes the snapshot
 5. Rotates the backup snapshots

# LICENSE

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