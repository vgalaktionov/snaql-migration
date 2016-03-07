{% sql 'create_roles' %}
  CREATE TABLE roles (
    id INT NOT NULL,
    title VARCHAR(100),
    PRIMARY KEY (id)
  )
{% endsql %}

{% sql 'create_users', depends_on=['create_roles'] %}
  CREATE TABLE users (
    id INT NOT NULL,
    role_id INT NOT NULL,
    name VARCHAR(100),
    PRIMARY KEY (id),
    FOREIGN KEY(role_id) REFERENCES roles (id)
  )
{% endsql %}