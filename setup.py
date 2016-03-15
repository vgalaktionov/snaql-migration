# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    long_description = readme_file.read()

setup(
    name='snaql-migration',
    version='0.1.0',
    author='Egor Komissarov',
    author_email='komissarex@gmail.com',
    license='MIT',
    packages=find_packages(),
    url='https://github.com/komissarex/snaql-migration',
    description='Lightweight SQL schema migration tool, based on Snaql query builder',
    install_requires=[
        'click==6.3',
        'snaql==0.3.5',
        'PyYAML==3.11'
    ],
    entry_points={
        'console_scripts': [
            'snaql-migration=snaql_migration.snaql_migration:snaql_migration'  # ¯\_(ツ)_/¯
        ]
    }
)