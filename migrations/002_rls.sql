-- ============================================================
-- Access control (Row Level Security). Run this too.
-- The web app uses the PUBLIC anon key: read-only on ACTIVE data.
-- Writes happen only with the service_role key (ingestion script, backend only), which bypasses RLS.
-- ============================================================
alter table source_versions enable row level security;
alter table chunks enable row level security;

drop policy if exists anon_read_active_sources on source_versions;
create policy anon_read_active_sources on source_versions for select to anon, authenticated using (status = 'active');

drop policy if exists anon_read_active_chunks on chunks;
create policy anon_read_active_chunks on chunks for select to anon, authenticated
  using (exists (select 1 from source_versions s where s.id = chunks.source_version_id and s.status = 'active'));

-- No insert/update/delete policies for anon/authenticated => those writes are denied.
revoke insert, update, delete on source_versions, chunks from anon, authenticated;
grant select on source_versions, chunks to anon, authenticated;
grant execute on function hybrid_search(text, vector, int) to anon, authenticated;
