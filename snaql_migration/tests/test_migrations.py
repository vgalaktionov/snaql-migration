try:
    import unittest2 as unittest
except ImportError:
    import unittest

from os import unlink

from click.testing import CliRunner

from snaql_migration.snaql_migration import DBWrapper, _parse_config, snaql_migration


class TestMigrations(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

        with open('tests/config.yml', 'rb') as f:
            self.config = _parse_config(f)

        self.db = DBWrapper(self.config['db_uri'])

    def tearDown(self):
        unlink('tests/test.db')

    def test_migrations_table_creation(self):
        self.assertIn('snaql_migrations', self.db.query(
            "SELECT * FROM sqlite_master "
            "WHERE type='table' AND name='snaql_migrations';").fetchone())

    def test_migrations_show(self):
        result = self.runner.invoke(snaql_migration, ['--config', 'tests/config.yml', 'show'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('users_app', result.output)
        self.assertIn('001-create-users', result.output)
        self.assertIn('002-update-users', result.output)

    def test_apply_all(self):
        result = self.runner.invoke(snaql_migration, ['--config', 'tests/config.yml', 'apply', 'all'])

        self.assertEqual(result.exit_code, 0)

        self.assertIn('countries', self.db.query(
            "SELECT * FROM sqlite_master "
            "WHERE type='table' AND name='countries';").fetchone())

        self.assertIn('users', self.db.query(
            "SELECT * FROM sqlite_master "
            "WHERE type='table' AND name='users';").fetchone())

        self.assertTrue(self.db.is_migration_applied('countries_app', '001-create-countries'))
        self.assertTrue(self.db.is_migration_applied('users_app', '001-create-users'))

    def test_revert(self):
        self.runner.invoke(snaql_migration, ['--config', 'tests/config.yml', 'apply', 'all'])

        result = self.runner.invoke(snaql_migration,
                                    ['--config', 'tests/config.yml', 'revert', 'users_app/002-update-users'])

        self.assertEqual(result.exit_code, 0)

        self.assertIsNone(self.db.query(
            "SELECT * FROM sqlite_master "
            "WHERE type='index' AND name='idx1';").fetchone()
              )

        self.assertFalse(self.db.is_migration_applied('users_app', '003-create-index'))
        self.assertFalse(self.db.is_migration_applied('users_app', '002-update-users'))
        self.assertTrue(self.db.is_migration_applied('users_app', '001-create-users'))
