{% sql 'revert_users' %}
  ALTER TABLE users
  DROP COLUMN surname;
{% endsql %}