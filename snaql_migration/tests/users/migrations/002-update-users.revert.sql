{% sql 'drop_users' %}
  ALTER TABLE users
  DROP surname;
{% endsql %}