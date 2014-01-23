XenBackup
=========
Backup virtual machines from a XenServer.

Example:

    xenbackup.py --host xenserver1 --user root --password pw --path=/var/xenbackup

# How it works

 * Retrives all the virtual machines running on the xenserver
 * Creates a snapshot
 * Downloads the snapshot
 * Deletes the snapshot
 * Rotates the backup snapshots
