create extension if not exists vector;

create table source_versions (
  id uuid primary key default gen_random_uuid(),
  source_id text not null,
  url text not null,
  title text not null,
  page_updated_on date,              -- from the page, when available
  fetched_at timestamptz not null,   -- UTC; a different fact from page_updated_on
  content_hash text not null,
  status text not null default 'staged' check (status in ('staged','active','retired')),
  reviewed_by text,
  reviewed_at timestamptz,
  unique (source_id, content_hash)
);

create table chunks (
  id text primary key,               -- stable ID shown in citations, e.g. graduate-overview#3
  source_version_id uuid not null references source_versions(id) on delete cascade,
  section_heading text not null,
  position int not null,
  text text not null,
  fts tsvector generated always as (to_tsvector('english', text)) stored,
  embedding vector(1536)             -- keep dimension identical to EMBEDDING_DIM
);

create index chunks_fts_idx on chunks using gin (fts);
create index chunks_embedding_idx on chunks using hnsw (embedding vector_cosine_ops);

-- Hybrid search: full-text + vector fused with reciprocal rank fusion (k=60).
create or replace function hybrid_search(q text, q_emb vector(1536), match_count int default 5)
returns table (chunk_id text, score float) language sql stable as $$
  with ft as (
    select c.id, row_number() over (order by ts_rank_cd(c.fts, websearch_to_tsquery('english', q)) desc) r
    from chunks c join source_versions s on s.id = c.source_version_id
    where s.status = 'active' and c.fts @@ websearch_to_tsquery('english', q)
    order by r limit 20
  ), vec as (
    select c.id, row_number() over (order by c.embedding <=> q_emb) r
    from chunks c join source_versions s on s.id = c.source_version_id
    where s.status = 'active' and c.embedding is not null
    order by r limit 20
  )
  select coalesce(ft.id, vec.id), coalesce(1.0/(60+ft.r),0) + coalesce(1.0/(60+vec.r),0) as score
  from ft full outer join vec on ft.id = vec.id
  order by score desc limit match_count;
$$;
