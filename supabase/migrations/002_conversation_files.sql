-- conversation_files: stores uploaded resume/document metadata
create table conversation_files (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  filename text not null,
  storage_path text not null,
  gemini_file_uri text not null,
  mime_type text not null,
  file_size bigint not null,
  created_at timestamptz not null default now()
);

create index idx_conversation_files_conversation on conversation_files(conversation_id);
create index idx_conversation_files_user on conversation_files(user_id);

alter table conversation_files enable row level security;

create policy "Users can read own files"
  on conversation_files for select
  using (user_id = auth.uid());

create policy "Users can insert own files"
  on conversation_files for insert
  with check (user_id = auth.uid());
