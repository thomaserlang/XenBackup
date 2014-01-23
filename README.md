XenBackup
=========
Backup virtual machines from a XenServer. Tested with Python 2.7.

Example:

    xenbackup.py --host xenserver1 --user root --password pw --path=/var/xenbackup

# Arguments
```
  -h, --help            show this help message and exit
  --path PATH           backup directory
  --host HOST           xenserver host
  --user USER           xenserver user
  --password PASSWORD   xenserver password
  --retry_max RETRY_MAX
                        max retries per VM
  --retry_delay RETRY_DELAY
                        number of seconds to wait after each failed try
  --rotate_snapshots ROTATE_SNAPSHOTS
                        enable rotate
  --rotate_snapshots_max ROTATE_SNAPSHOTS_MAX
                        maximum number of snapshots stored in a directory
```

# How it works

 1. Retrives all the virtual machines running on the XenServer
 2. Creates a snapshot
 3. Downloads the snapshot
 4. Deletes the snapshot
 5. Rotates the backup snapshots

# Missing

 * External logging (Maybe Syslog)
 * VM white/blacklist
