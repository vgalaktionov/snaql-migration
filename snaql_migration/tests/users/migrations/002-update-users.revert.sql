{# unfortunately, SQLite does not accept ALTER TABLE users DROP COLUMN surname; syntax =/ #}

{% sql 'drop_users' %}
  DROP TABLE users;
{% endsql %}

{% sql 'recreate_users', depends_on=['drop_users'] %}
  CREATE TABLE users (
    id INT NOT NULL,
    role_id INT NOT NULL,
    name VARCHAR(100),
    PRIMARY KEY (id),
    FOREIGN KEY(role_id) REFERENCES roles (id)
  )
{% endsql %}