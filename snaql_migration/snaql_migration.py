# -*- coding: utf-8 -*-
"""
    snaql-migration
    ~~~~~~~~~~~~~~~

    Lightweight SQL schema migration tool, based on Snaql query builder.

    :copyright: (c) 2016 by Egor Komissarov.
    :license: MIT, see LICENSE for more details.
"""

import warnings

import os

from datetime import datetime

try:
    from urllib.parse import urlparse, unquote
except ImportError:
    from urlparse import urlparse
    from urllib2 import unquote as unquote

import click
import yaml
from snaql.factory import Snaql

__version__ = '0.1.2'


@click.group()
@click.option('--db-uri', default=None, help='Database URI, ignored if --config is set')
@click.option('--migrations', default=None, help='Migrations location, ignored if --config is set',
              type=click.Path(exists=True))
@click.option('--app', default=None, help='App name, ignored if --config is set')
@click.option('--config', default=None,
              help='Configuration file, overlaps usage of the --db-uri/--migrations/--app group', type=click.File('rb'))
@click.pass_context
def snaql_migration(ctx, db_uri, migrations, app, config):
    """
    Lightweight SQL Schema migration tool based on Snaql queries
    """

    if config:
        migrations_config = _parse_config(config)
    else:
        if db_uri and migrations and app:
            migrations_config = _generate_config(db_uri, migrations, app)
        else:
            raise click.ClickException('If --config is not set, then --db-uri, --migrations and --app must be provided')

    ctx.obj = {
        'config': migrations_config
    }

    try:
        ctx.obj['db'] = DBWrapper(ctx.obj['config']['db_uri'])
    except Exception as e:
        raise click.ClickException('Unable to connect to database, exception is "{0}"'.format(str(e)))


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

    if name != 'all':  # specific migration
        try:
            app_name, target_migration = name.split('/', 2)
        except ValueError:
            raise click.ClickException("NAME format is <app>/<migration> or 'all'")

        apps = ctx.obj['config']['apps']
        if app_name not in apps.keys():
            raise click.ClickException('unknown app "{0}"'.format(app_name))

        app = apps[app_name]
        migrations = app['migrations']
        if target_migration not in migrations:
            raise click.ClickException('unknown migration "{0}"'.format(name))

        migrations = migrations[:migrations.index(target_migration) + 1]  # including all prevoius migrations
        for migration in migrations:
            click.echo(click.style('Applying {0}...'.format(click.style(migration, bold=True)), fg='blue'))

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
                click.echo(click.style('  FAILED.', fg='red'))
                ctx.obj['db'].rollback()
                raise click.ClickException('migration execution failed\n{0}'.format(e))

            click.echo(click.style('  OK.', fg='green'))

            ctx.obj['db'].commit()

            ctx.obj['db'].fix_migration(app_name, migration)

    else:  # migrate everything
        for app_name, app in ctx.obj['config']['apps'].items():
            click.echo(click.style('Migrating {0}...'.format(click.style(app_name, bold=True)), fg='blue'))

            for migration in app['migrations']:
                click.echo('  Applying {0}...'.format(click.style(migration, bold=True)))

                if ctx.obj['db'].is_migration_applied(app_name, migration):
                    click.echo(click.style('    SKIPPED.', fg='green'))
                    continue

                try:
                    snaql_factory = Snaql(app['path'], '')
                    queries = snaql_factory.load_queries(migration + '.apply.sql').ordered_blocks

                    for query in queries:
                        if verbose:
                            click.echo('    ' + query())

                        ctx.obj['db'].query(query())

                except Exception as e:
                    click.echo(click.style('    FAILED.', fg='red'))
                    ctx.obj['db'].rollback()
                    raise click.ClickException('migration execution failed\n{0}'.format(e))

                click.echo(click.style('  OK.', fg='green'))

                ctx.obj['db'].commit()

                ctx.obj['db'].fix_migration(app_name, migration)


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

    mig_idx = migrations.index(target_migration)
    migrations = migrations[-len(migrations) + mig_idx:]  # all migrations after target_migration
    migrations = migrations[::-1]  # in reversed order

    for migration in migrations:
        click.echo(
            click.style('Reverting {0}...'.format(click.style(app_name + '/' + migration, bold=True)), fg='blue'))

        if not ctx.obj['db'].is_migration_applied(app_name, migration):
            click.echo(click.style('  SKIPPED.', fg='green'))
            continue
        try:
            snaql_factory = Snaql(app['path'], '')
            queries = snaql_factory.load_queries(migration + '.revert.sql').ordered_blocks

            for query in queries:
                if verbose:
                    click.echo('    ' + query())

                ctx.obj['db'].query(query())

        except Exception as e:
            click.echo(click.style('  FAILED.', fg='red'))
            ctx.obj['db'].rollback()

            raise click.ClickException('migration execution failed\n{0}'.format(e))

        click.echo(click.style('  OK.', fg='green'))

        ctx.obj['db'].commit()

        ctx.obj['db'].revert_migration(app_name, migration)


def _collect_migrations(migrations_dir):
    migrations = []

    for root, dir, files in os.walk(migrations_dir):
        for file in [f for f in files if f.endswith('.apply.sql') or f.endswith('.revert.sql')]:
            migration = os.path.join(root, file).lstrip(migrations_dir + '/').rsplit('.', 2)[0]
            migrations.append(migration)

    migrations = sorted(set(migrations))

    for migration in migrations:
        if not os.path.isfile(os.path.join(migrations_dir, migration + '.apply.sql')) \
                or not os.path.isfile(os.path.join(migrations_dir, migration + '.revert.sql')):
            raise click.ClickException('One of the .apply.sql or .revert.sql files '
                                       'is absent for migration \'{0}\''.format(migration))

    return migrations


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


def _generate_config(db_uri, migrations, app):
    return {
        'db_uri': db_uri,
        'apps': {
            app: {
                'path': migrations,
                'migrations': _collect_migrations(migrations)
            }
        }
    }


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

        if url['scheme'] == 'postgres':
            try:
                import psycopg2
            except ImportError:
                raise click.ClickException('Package psycopg2 must be installed for PostgreSQL use')

            self.db = psycopg2.connect(host=url['host'], port=url['port'], user=url['username'],
                                       password=url['password'], database=url['path'])
        elif url['scheme'] == 'mysql':
            try:
                import pymysql
            except ImportError:
                raise click.ClickException('Package pymysql must be installed for MySQL use')

            self.db = pymysql.connect(host=url['host'], port=url['port'], user=url['username'],
                                      passwd=url['password'], db=url['path'])
        else:
            raise click.ClickException('Unsupported db connection type "{0}"'.format(url['scheme']))

        self._prepare_migrations_table()

    def _prepare_migrations_table(self):
        warnings.simplefilter("ignore")
        self.query('CREATE TABLE IF NOT EXISTS snaql_migrations ('
                   'app VARCHAR(50) NOT NULL,'
                   'migration VARCHAR(50) NOT NULL,'
                   'applied TIMESTAMP NOT NULL,'
                   'PRIMARY KEY (app, migration))')
        self.commit()

    def query(self, sql, *args):
        return self.db.cursor().execute(sql, *args)  # note: there is no autocommit

    def query_one(self, sql, *args):
        with self.db.cursor() as cur:
            cur.execute(sql, *args)
            result = cur.fetchone()
            self.commit()
            return result

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()

    def is_migration_applied(self, app, migration):
        return self.query_one('SELECT EXISTS(SELECT 1 FROM snaql_migrations '
                              'WHERE app=%s AND migration=%s)',
                              [app, migration])[0]

    def fix_migration(self, app, migration):
        self.query('INSERT INTO snaql_migrations(app, migration, applied) '
                   'VALUES (%s, %s, %s)',
                   [app, migration, datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        self.commit()

    def revert_migration(self, app, migration):
        self.query('DELETE FROM snaql_migrations WHERE app=%s AND migration=%s', [app, migration])
        self.commit()

    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()


snaql_migration.add_command(show)
snaql_migration.add_command(apply)
snaql_migration.add_command(revert)


if __name__ == '__main__':
    snaql_migration()
