{% sql 'create_roles' %}
  CREATE TABLE roles (
    id INT NOT NULL,
    title VARCHAR(100),
    PRIMARY KEY (id)
  )
{% endsql %}