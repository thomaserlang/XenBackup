#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='XenBackup',
    version='0.0.2',
    author='Thomas Erlang',
    author_email='thomas@erlang.dk',
    url='https://github.com/thomaserlang/xenbackup',
    description='Easy backup of virtual machines running on a XenServer',
    zip_safe=False,
    license='MIT',
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'xenbackup = xenbackup.xenbackup:main',
        ],
    },
    package_dir={'': 'xenbackup'},
    packages=find_packages('xenbackup'),
)