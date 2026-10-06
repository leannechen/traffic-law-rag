SELECT m.string_value AS law, COUNT(*) AS chunks
  FROM embedding_metadata m
  WHERE m.key = 'law_short_name'
  GROUP BY m.string_value;