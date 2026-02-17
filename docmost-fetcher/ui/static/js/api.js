export async function fetchSpaces(){
  const r = await fetch('/api/spaces');
  const data = await r.json();
  if (!data.ok) throw new Error('spaces failed');
  return data.spaces || [];
}

export async function fetchPages(spaceId){
  const r = await fetch(`/api/spaces/${encodeURIComponent(spaceId)}/pages`);
  const data = await r.json();
  if (!data.ok) throw new Error('pages failed');
  return data.pages || [];
}

export async function postChat(payload){
  const r = await fetch('/api/chat', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload),
  });

  const data = await r.json().catch(()=> ({}));
  if (!r.ok || !data.ok) {
    throw new Error(`chat failed: ${r.status} ${JSON.stringify(data)}`);
  }
  return data;
}
