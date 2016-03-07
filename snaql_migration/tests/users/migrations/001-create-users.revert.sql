{% sql 'revert_users' %}
  DROP TABLE users;
{% endsql %}

{% sql 'revert_roles', depends_on=['revert_users'] %}
  DROP TABLE roles;
{% endsql %}