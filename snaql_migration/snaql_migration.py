# -*- coding: utf-8 -*-
"""
    snaql-migration
    ~~~~~~~~~~~~~~~

    Lightweight SQL schema migration tool, based on Snaql query builder.

    Every migration must be stored in a couple of SQL files:
      - some_migration.apply.sql
      - some_migration.revert.sql

    YAML-config file format:

      db_uri: 'sqlite:///tests/test.db'

      migrations:
        first_app: 'first_app_location/migrations'
        second_app: 'irst_app_location/migrations'


    :copyright: (c) 2016 by Egor Komissarov.
    :license: MIT, see LICENSE for more details.
"""

import os
from datetime import datetime
from urllib.parse import urlparse, unquote

import click
import yaml
from snaql.factory import Snaql

__version__ = '0.0.2'


@click.group()
@click.option('--config', default='config.yml', help='Configuration file', type=click.File('rb'))
@click.pass_context
def snaql_migration(ctx, config):
    """
    Lightweight SQL Schema migration tool based on Snaql queries
    """

    ctx.obj = {'config': _parse_config(config)}

    try:
        ctx.obj['db'] = DBWrapper(ctx.obj['config']['db_uri'])
    except Exception as e:
        raise click.ClickException('Unable to connect to database\n' + str(e))


@click.command()
@click.pass_context
def show(ctx):
    """
    Show migrations list
    """

    for app_name, app in ctx.obj['config']['apps'].items():
        click.echo(click.style(app_name, fg='green', bold=True))
        for migration in app['migrations']:
            applied = ctx.obj['db'].is_migration_applied(app_name, migration)
            click.echo('  {0} {1}'.format(migration, click.style('(applied)', bold=True) if applied else ''))


@click.command()
@click.argument('name')
@click.option('--verbose', is_flag=True, default=False, help='Dump SQL queries')
@click.pass_context
def apply(ctx, name, verbose):
    """
    Apply migration
    """

    if name == 'all':  # TODO: implement specific migration apply

        for app_name, app in ctx.obj['config']['apps'].items():
            click.echo(click.style('Migrating {0}...'.format(click.style(app_name, bold=True)), fg='blue'))

            for migration in app['migrations']:
                click.echo('  Executing {0}...'.format(click.style(migration, bold=True)))

                if ctx.obj['db'].is_migration_applied(app_name, migration):
                    click.echo(click.style('  SKIPPED.', fg='green'))
                    continue

                try:
                    snaql_factory = Snaql(app['path'], '')
                    queries = snaql_factory.load_queries(migration + '.apply.sql').ordered_blocks
                    for query in queries:
                        if verbose:
                            click.echo('    ' + query())
                        ctx.obj['db'].query(query())
                except Exception as e:
                    click.echo(click.style('  FAIL.', fg='red'))
                    raise click.ClickException('migration execution failed\n{0}'.format(e))

                ctx.obj['db'].fix_migration(app_name, migration)

                ctx.obj['db'].commit()

                click.echo(click.style('  OK.', fg='green'))


@click.command()
@click.argument('name')
@click.option('--verbose', is_flag=True, default=False, help='Dump SQL queries')
@click.pass_context
def revert(ctx, name, verbose):
    """
    Revert migration
    """

    try:
        app_name, target_migration = name.split('/', 2)
    except ValueError:
        raise click.ClickException('NAME format is <app>/<migration>')

    apps = ctx.obj['config']['apps']
    if app_name not in apps.keys():
        raise click.ClickException('unknown app "{0}"'.format(app_name))

    app = apps[app_name]
    migrations = app['migrations']
    if target_migration not in migrations:
        raise click.ClickException('unknown migration "{0}"'.format(name))

    try:
        mig_idx = migrations.index(target_migration)
        for migration in reversed(migrations[-len(migrations) + mig_idx:]):  # all migrations after target_migration
            click.echo(
                click.style('Reverting {0}...'.format(click.style(app_name + '/' + migration, bold=True)), fg='blue'))

            if not ctx.obj['db'].is_migration_applied(app_name, migration):
                click.echo(click.style('  SKIPPED.', fg='green'))
                continue

            snaql_factory = Snaql(app['path'], '')
            queries = snaql_factory.load_queries(migration + '.revert.sql').ordered_blocks
            for query in queries:
                if verbose:
                    click.echo('    ' + query())
                ctx.obj['db'].query(query())

            click.echo(click.style('  OK.', fg='green'))

            ctx.obj['db'].revert_migration(app_name, migration)

    except Exception as e:
        click.echo(click.style('  FAIL.', fg='red'))
        ctx.obj['db'].rollback()
        raise click.ClickException('migration execution failed\n{0}'.format(e))

    ctx.obj['db'].commit()


def _collect_migrations(migrations_dir):
    migrations = []

    for root, dir, files in os.walk(migrations_dir):
        for file in [f for f in files if f.endswith('.apply.sql') or f.endswith('.revert.sql')]:
            migration = os.path.join(root, file).lstrip(migrations_dir + '/').rsplit('.', 2)[0]
            migrations.append(migration)

    return sorted(set(migrations))


def _parse_config(config_file):
    try:
        config = yaml.load(config_file)
    except yaml.YAMLError:
        raise click.ClickException('Incorrect YAML config file format')

    if 'db_uri' not in config:
        raise click.ClickException('db_uri must be specified in config file')
    if 'migrations' not in config or not config['migrations']:
        raise click.ClickException('at least one migration must be specified in config file')

    # reformatting to the {apps: {app1: {path: /some_path, migrations: [...]}}} format
    apps = {}
    for app, path in config['migrations'].items():
        apps[app] = {'path': path, 'migrations': _collect_migrations(path)}

    del config['migrations']
    config['apps'] = apps

    return config


class DBWrapper:
    def __init__(self, db_url):
        parsed = urlparse(db_url)
        url = {
            'scheme': parsed.scheme,
            'host': parsed.hostname,
            'path': unquote(parsed.path).lstrip('/'),
            'username': None,
            'password': None,
            'port': None
        }
        if parsed.username:
            url['username'] = unquote(parsed.username)
        if parsed.password:
            url['password'] = unquote(parsed.password)
        if parsed.port:
            url['port'] = int(parsed.port)

        if url['scheme'] == 'sqlite':
            import sqlite3
            self.db = sqlite3.connect(url['path'])
        elif url['scheme'] == 'mysql+pymysql':
            import pymysql
            self.db = pymysql.connect(host=url['host'], port=url['port'], user=url['username'],
                                      passwd=url['password'], db=url['path'])
        else:
            raise click.ClickException('unsupported db connection type "{0}"'.format(url['scheme']))

        self._prepare_migrations_table()

    def _prepare_migrations_table(self):
        self.query('CREATE TABLE IF NOT EXISTS snaql_migrations ('
                   'app VARCHAR(50) NOT NULL,'
                   'migration VARCHAR(50) NOT NULL,'
                   'applied DATETIME NOT NULL,'
                   'PRIMARY KEY (app, migration))')

        self.commit()

    def query(self, sql, **kwargs):
        return self.db.cursor().execute(sql, kwargs)

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()

    def is_migration_applied(self, app, migration):
        return self.query('SELECT EXISTS(SELECT 1 FROM snaql_migrations WHERE app=:app AND migration=:migration)',
                          app=app, migration=migration).fetchone()[0]

    def fix_migration(self, app, migration):
        self.query('INSERT INTO snaql_migrations(app, migration, applied) '
                   'VALUES (:app, :migration, :date)',
                   app=app,
                   migration=migration,
                   date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    def revert_migration(self, app, migration):
        self.query('DELETE FROM snaql_migrations WHERE app=:app AND migration=:migration', app=app,
                   migration=migration)

    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()


# TODO: implement CREATE command

snaql_migration.add_command(show)
snaql_migration.add_command(apply)
snaql_migration.add_command(revert)

if __name__ == '__main__':
    snaql_migration()
