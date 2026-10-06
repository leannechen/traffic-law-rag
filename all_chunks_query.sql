SELECT e.embedding_id            AS chunk_id,
         MAX(CASE WHEN m.key='law_short_name' THEN m.string_value END) AS law,
         MAX(CASE WHEN m.key='article_no'     THEN m.string_value END) AS article_no,
         MAX(CASE WHEN m.key='paragraph_no'   THEN m.int_value    END) AS paragraph_no,
         LENGTH(MAX(CASE WHEN m.key='chroma:document' THEN m.string_value END)) AS chars,
         SUBSTR(MAX(CASE WHEN m.key='chroma:document' THEN m.string_value END), 1, 40) AS head
  FROM embeddings e
  JOIN embedding_metadata m ON m.id = e.id
  GROUP BY e.embedding_id
  ORDER BY e.embedding_id;