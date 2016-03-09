{% sql 'create_index' %}
  CREATE INDEX idx1
  ON users (surname);
{% endsql %}