try:
    import unittest2 as unittest
except ImportError:
    import unittest

from click.testing import CliRunner

from snaql_migration.snaql_migration import DBWrapper, _parse_config, snaql_migration


class TestMigrations(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

        with open('tests/config.yml', 'rb') as f:
            self.config = _parse_config(f)

        self.db = DBWrapper(self.config['db_uri'])

    def tearDown(self):
        # TODO: refactor!
        self.runner.invoke(snaql_migration, ['--config', 'tests/config.yml', 'revert', 'users_app/001-create-users'])


    def test_migrations_table_creation(self):
        self.assertIsNotNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_tables "
            "WHERE tablename='snaql_migrations';"))

    def test_migrations_show(self):
        result = self.runner.invoke(snaql_migration, ['--config', 'tests/config.yml', 'show'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('users_app', result.output)
        self.assertIn('001-create-users', result.output)
        self.assertIn('002-update-users', result.output)

    def test_apply_all(self):
        result = self.runner.invoke(snaql_migration, ['--config', 'tests/config.yml', 'apply', 'all'])

        self.assertEqual(result.exit_code, 0)

        self.assertIsNotNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_tables "
            "WHERE tablename='countries';"))

        self.assertIsNotNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_tables "
            "WHERE tablename='countries';"))

        self.assertIsNotNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_indexes "
            "WHERE indexname='idx1';"))

        self.assertTrue(self.db.is_migration_applied('countries_app', '001-create-countries'))
        self.assertTrue(self.db.is_migration_applied('users_app', '001-create-users'))

    def test_apply_specific(self):
        result = self.runner.invoke(snaql_migration,
                                    ['--config', 'tests/config.yml', 'apply', 'users_app/002-update-users'])

        self.assertEqual(result.exit_code, 0)

        self.assertIsNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_indexes "
            "WHERE indexname='idx1';"))

        self.assertTrue(self.db.is_migration_applied('users_app', '001-create-users'))
        self.assertTrue(self.db.is_migration_applied('users_app', '002-update-users'))
        self.assertFalse(self.db.is_migration_applied('users_app', '003-create-index'))

    def test_revert(self):
        self.runner.invoke(snaql_migration, ['--config', 'tests/config.yml', 'apply', 'all'])

        result = self.runner.invoke(snaql_migration,
                                    ['--config', 'tests/config.yml', 'revert', 'users_app/002-update-users'])

        self.assertEqual(result.exit_code, 0)

        self.assertIsNone(self.db.query_one(
            "SELECT * FROM pg_catalog.pg_indexes "
            "WHERE indexname='idx1';"))

        self.assertFalse(self.db.is_migration_applied('users_app', '003-create-index'))
        self.assertFalse(self.db.is_migration_applied('users_app', '002-update-users'))
        self.assertTrue(self.db.is_migration_applied('users_app', '001-create-users'))
