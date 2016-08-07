import yaml

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from click.testing import CliRunner

from snaql_migration.snaql_migration import DBWrapper, snaql_migration


class TestMigrations(unittest.TestCase):
    CONFIG_VALID = 'snaql_migration/tests/config.yml'
    CONFIG_INVALID = 'snaql_migration/tests/config_broken.yml'

    def setUp(self):
        self.runner = CliRunner()

        with open('snaql_migration/tests/db_uri.yml', 'rb') as f:
            self.db_uri = yaml.load(f)['db_uri']

        try:
            self.db = DBWrapper(self.db_uri)
        except Exception:
            self.fail("Unable to connect to database")

        # generating config files
        with open(TestMigrations.CONFIG_VALID, 'w') as f:
            f.writelines('db_uri: "{0}"\r\n'
                         'migrations:\r\n'
                         '    users_app: "snaql_migration/tests/users/migrations"\r\n'
                         '    countries_app: "snaql_migration/tests/countries/migrations"'.format(self.db_uri))

        with open(TestMigrations.CONFIG_INVALID, 'w') as f:  # points to broken migrations
            f.writelines('db_uri: "{0}"\r\n'
                         'migrations:\r\n'
                         '    users_app: "snaql_migration/tests/users/migrations_broken"\r\n'.format(self.db_uri))

        # initial db cleanup
        self.db.query("DROP TABLE IF EXISTS users;")
        self.db.query("DROP TABLE IF EXISTS roles CASCADE;")
        self.db.query("DROP TABLE IF EXISTS countries;")
        self.db.query("DROP TABLE IF EXISTS snaql_migrations;")
        self.db.query("DROP INDEX IF EXISTS idx1;")

        self.db.commit()

    def test_migrations_table_creation(self):
        self.db._prepare_migrations_table()

        self.assertIsNotNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_tables "
            "WHERE tablename='snaql_migrations';"))

    def test_migrations_show(self):
        result = self.runner.invoke(snaql_migration, ['--config', TestMigrations.CONFIG_VALID, 'show'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('users_app', result.output)
        self.assertIn('countries_app', result.output)
        self.assertIn('001-create-users', result.output)
        self.assertIn('002-update-users', result.output)

    def test_migrations_show_without_config(self):
        result = self.runner.invoke(snaql_migration,
                                    ['--db-uri', self.db_uri, '--migrations', 'snaql_migration/tests/users/migrations',
                                     '--app', 'users_app', 'show'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('users_app', result.output)
        self.assertIn('001-create-users', result.output)
        self.assertIn('002-update-users', result.output)

    def test_apply_all(self):
        result = self.runner.invoke(snaql_migration, ['--config', TestMigrations.CONFIG_VALID, 'apply', 'all'])

        self.assertEqual(result.exit_code, 0)

        self.assertIsNotNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_tables "
            "WHERE tablename='countries';"))

        self.assertIsNotNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_tables "
            "WHERE tablename='users';"))

        self.assertIsNotNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_indexes "
            "WHERE indexname='idx1';"))

        self.assertTrue(self.db.is_migration_applied('countries_app', '001-create-countries'))
        self.assertTrue(self.db.is_migration_applied('users_app', '001-create-users'))

    def test_apply_specific(self):
        result = self.runner.invoke(snaql_migration,
                                    ['--config', TestMigrations.CONFIG_VALID, 'apply', 'users_app/002-update-users'])

        self.assertEqual(result.exit_code, 0)

        self.assertIsNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_indexes "
            "WHERE indexname='idx1';"))

        self.assertTrue(self.db.is_migration_applied('users_app', '001-create-users'))
        self.assertTrue(self.db.is_migration_applied('users_app', '002-update-users'))
        self.assertFalse(self.db.is_migration_applied('users_app', '003-create-index'))

    def test_revert(self):
        self.runner.invoke(snaql_migration, ['--config', TestMigrations.CONFIG_VALID, 'apply', 'all'])

        result = self.runner.invoke(snaql_migration,
                                    ['--config', TestMigrations.CONFIG_VALID, 'revert', 'users_app/002-update-users'])

        self.assertEqual(result.exit_code, 0)

        self.assertIsNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_indexes "
            "WHERE indexname='idx1';"))

        self.assertFalse(self.db.is_migration_applied('users_app', '003-create-index'))
        self.assertFalse(self.db.is_migration_applied('users_app', '002-update-users'))
        self.assertTrue(self.db.is_migration_applied('users_app', '001-create-users'))

    def test_apply_broken(self):
        result = self.runner.invoke(snaql_migration,
                                    ['--config', TestMigrations.CONFIG_INVALID, 'apply', 'all'])

        self.assertNotEqual(result.exit_code, 0)

        self.assertIsNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_tables "
            "WHERE tablename='users';"))

        self.assertIsNotNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_tables "
            "WHERE tablename='roles';"))

        self.assertTrue(self.db.is_migration_applied('users_app', '001-create-roles'))
        self.assertFalse(self.db.is_migration_applied('users_app', '002-create-users'))

    def test_revert_broken(self):
        self.runner.invoke(snaql_migration, ['--config', TestMigrations.CONFIG_INVALID, 'apply', 'all'])

        result = self.runner.invoke(snaql_migration,
                                    ['--config', TestMigrations.CONFIG_INVALID, 'revert', 'users_app/001-create-roles'])

        self.assertNotEqual(result.exit_code, 0)

        self.assertIsNotNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_tables "
            "WHERE tablename='roles';"))

        self.assertIsNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_tables "
            "WHERE tablename='users';"))

        self.assertTrue(self.db.is_migration_applied('users_app', '001-create-roles'))
        self.assertFalse(self.db.is_migration_applied('users_app', '002-create-users'))
