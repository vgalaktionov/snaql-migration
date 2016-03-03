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

import click
import records
import yaml
from snaql.factory import Snaql
from sqlalchemy.exc import SQLAlchemyError

__version__ = '0.0.1'


@click.group()
@click.option('--config', default='config.yml', help='Configuration file', type=click.File('rb'))
@click.pass_context
def snaql_migration(ctx, config):
    """
    Lightweight SQL Schema migration tool based on Snaql queries
    """

    ctx.obj = {'config': _parse_config(config)}

    try:
        ctx.obj['db'] = records.Database(ctx.obj['config']['db_uri'])
    except SQLAlchemyError as e:
        raise click.ClickException('Unable to connect to database\n' + str(e))

    _prepare_migrations_table(ctx.obj['db'])


@click.command()
@click.pass_context
def show(ctx):
    """
    Show migrations list
    """

    for app_name, app in ctx.obj['config']['apps'].items():
        click.echo(click.style(app_name, fg='green', bold=True))
        for migration in app['migrations']:
            applied = _already_applied(ctx.obj['db'], app_name, migration)
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

                if _already_applied(ctx.obj['db'], app_name, migration):
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

                _fix_migration(ctx.obj['db'], app_name, migration)

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
        app_name, migration = name.split('/', 2)
    except ValueError:
        raise click.ClickException('NAME format is <app>/<migration>')

    apps = ctx.obj['config']['apps']
    if app_name not in apps.keys():
        raise click.ClickException('unknown app "{0}"'.format(app_name))

    app = apps[app_name]
    if migration not in app['migrations']:
        raise click.ClickException('unknown migration "{0}"'.format(name))

    click.echo(click.style('Reverting {0}...'.format(click.style(name, bold=True)), fg='blue'))
    if not _already_applied(ctx.obj['db'], app_name, migration):
        return click.echo(click.style('  SKIPPED.', fg='green'))

    try:
        # TODO: revert all subsequent migrations
        snaql_factory = Snaql(app['path'], '')
        queries = snaql_factory.load_queries(migration + '.revert.sql').ordered_blocks
        for query in queries:
            if verbose:
                click.echo('    ' + query())
            ctx.obj['db'].query(query())
    except Exception as e:
        click.echo(click.style('  FAIL.', fg='red'))
        raise click.ClickException('migration execution failed\n{0}'.format(e))

    _revert_migration(ctx.obj['db'], app_name, migration)

    click.echo(click.style('  OK.', fg='green'))


def _prepare_migrations_table(db):
    db.query('CREATE TABLE IF NOT EXISTS snaql_migrations ('
             'app VARCHAR(50) NOT NULL,'
             'migration VARCHAR(50) NOT NULL,'
             'applied DATETIME NOT NULL,'
             'PRIMARY KEY (app, migration))')


def _fix_migration(db, app, migration):
    db.query('INSERT INTO snaql_migrations(app, migration, applied) '
             'VALUES (:app, :migration, :date)',
             app=app,
             migration=migration,
             date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


def _revert_migration(db, app, migration):
    db.query('DELETE FROM snaql_migrations WHERE app=:app AND migration=:migration', app=app, migration=migration)


def _already_applied(db, app, migration):
    return db.query('SELECT EXISTS(SELECT 1 FROM snaql_migrations '
                    'WHERE app=:app AND migration=:migration)',
                    app=app,
                    migration=migration)[0][0]


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

    apps = {}
    for app, path in config['migrations'].items():
        apps[app] = {'path': path, 'migrations': _collect_migrations(path)}

    del config['migrations']
    config['apps'] = apps

    return config


# TODO: implement CREATE command

snaql_migration.add_command(show)
snaql_migration.add_command(apply)
snaql_migration.add_command(revert)

if __name__ == '__main__':
    snaql_migration()
