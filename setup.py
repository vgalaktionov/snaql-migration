from setuptools import setup

setup(
    name='snaql-migration',
    version='0.0.4',
    py_modules=['snaql_migration'],
    include_package_data=True,
    install_requires=[
        'click==6.3',
        'snaql==0.3.5',
        'PyYAML==3.11'
    ],
    entry_points='''
        [console_scripts]
        snaql-migration=snaql_migration:snaql_migration
    ''',
)