#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='XenBackup',
    version='0.0.3',
    author='Thomas Erlang',
    author_email='thomas@erlang.dk',
    url='https://github.com/thomaserlang/xenbackup',
    description='Easy backup of virtual machines running on a XenServer',
    package_dir={'': 'src'},
    packages=find_packages('src'),
    zip_safe=False,
    install_requires=[],
    extras_require={},
    license=None,
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'xenbackup = xenbackup.xenbackup:main',
        ],
    },
    classifiers=[],
)