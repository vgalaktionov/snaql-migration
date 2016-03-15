try:
    import unittest2 as unittest
except ImportError:
    import unittest

from io import StringIO

from click import ClickException
from click.testing import CliRunner

from snaql_migration.snaql_migration import snaql_migration, _parse_config, _collect_migrations


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_collect_migrations(self):
        self.assertEqual(_collect_migrations('snaql_migration/tests/users/migrations'),
                         ['001-create-users',
                          '002-update-users',
                          '003-create-index'
                          ])

    def test_parse_config(self):
        # invalid db uri
        input = StringIO(u'db_urii: "postgres://test:@localhost/test"')
        self.assertRaises(ClickException, _parse_config, input)

        # no migrations defined
        input = StringIO(u'db_uri: "postgres://test:@localhost/test"\r\n'
                         u'migrations: \r\n')
        self.assertRaises(ClickException, _parse_config, input)

        input = StringIO(u'db_uri: "{0}"\r\n'
                         u'migrations:\r\n'
                         u'    users_app: "snaql_migration/tests/users/migrations"\r\n'
                         u'    countries_app: "snaql_migration/tests/countries/migrations"')

        # valid config
        config = _parse_config(input)
        self.assertIn('db_uri', config)
        self.assertEqual(config['apps'], {
            'users_app': {
                'migrations': ['001-create-users', '002-update-users', '003-create-index'],
                'path': 'snaql_migration/tests/users/migrations'
            },
            'countries_app': {
                'migrations': ['001-create-countries'],
                'path': 'snaql_migration/tests/countries/migrations'
            }})

    def test_invalid_config(self):
        result = self.runner.invoke(snaql_migration, ['--config', 'invalid.yml'])
        self.assertEqual(result.exit_code, 2)
