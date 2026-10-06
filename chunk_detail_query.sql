SELECT e.embedding_id AS chunk_id, m.string_value AS text
  FROM embeddings e
  JOIN embedding_metadata m ON m.id = e.id AND m.key = 'chroma:document'
  WHERE e.embedding_id IN ('K0040012:93', 'D0080090:1', 'K0040012:35-p3',
                           'K0040013:39-1-p2', 'K0040013:39-1-p4');