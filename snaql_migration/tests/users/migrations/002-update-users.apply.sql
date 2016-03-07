{% sql 'alter_users' %}
  ALTER TABLE users
  ADD COLUMN surname VARCHAR(50);
{% endsql %}