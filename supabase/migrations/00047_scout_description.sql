alter table public.scouts
  add column if not exists description text;

comment on column public.scouts.topic is
  'Comma-separated short tags for organizing scouts. Prefer 1-3 labels; do not store long criteria here.';

comment on column public.scouts.description is
  'Optional human-readable scout context. Filtering and notification rules belong in criteria.';
