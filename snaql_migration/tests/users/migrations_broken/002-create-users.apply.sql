{% sql 'create_users' %}
  CREATE TABLE users (
    id INT NOT NULL,
    role_id INT NOT NULLL, /* typo */
    name VARCHAR(100),
    PRIMARY KEY (id),
    FOREIGN KEY(role_id) REFERENCES roles (id)
  )
{% endsql %}