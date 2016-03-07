{% sql 'create_countries' %}
  CREATE TABLE countries (
    id INT NOT NULL,
    name VARCHAR(100),
    PRIMARY KEY (id)
  )
{% endsql %}