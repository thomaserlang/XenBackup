XenBackup
=========
Backup virtual machines from a XenServer.

Example:

    xenbackup.py --host xenserver1 --user root --password pw --path=/var/xenbackup

# How it works

 1. Retrives all the virtual machines running on the xenserver
 2. Creates a snapshot
 3. Downloads the snapshot
 4. Deletes the snapshot
 5. Rotates the backup snapshots
