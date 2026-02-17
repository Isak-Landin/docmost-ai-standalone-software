import { esc, isInteractiveTarget } from './util.js';
import { state } from './state.js';

export function buildTree(pages){
  state.pagesById = new Map();
  state.rootIds = [];

  for (const p of pages){
    state.pagesById.set(p.id, { ...p, children: [] });
  }

  for (const p of state.pagesById.values()){
    const parentId = p.parent_page_id;
    if (!parentId){ state.rootIds.push(p.id); continue; }
    const parent = state.pagesById.get(parentId);
    if (!parent){ state.rootIds.push(p.id); continue; }
    parent.children.push(p.id);
  }

  for (const p of state.pagesById.values()){
    p.children.sort((a,b)=>{
      const pa = state.pagesById.get(a), pb = state.pagesById.get(b);
      const ta = (pa?.title || '').toLowerCase();
      const tb = (pb?.title || '').toLowerCase();
      if (ta < tb) return -1;
      if (ta > tb) return 1;
      return (pa?.id || '').localeCompare(pb?.id || '');
    });
  }

  state.rootIds.sort((a,b)=>{
    const pa = state.pagesById.get(a), pb = state.pagesById.get(b);
    const ta = (pa?.title || '').toLowerCase();
    const tb = (pb?.title || '').toLowerCase();
    if (ta < tb) return -1;
    if (ta > tb) return 1;
    return (pa?.id || '').localeCompare(pb?.id || '');
  });
}

function setExpanded(childrenEl, toggleEl, expanded){
  childrenEl.classList.toggle('hidden', !expanded);
  toggleEl.textContent = expanded ? '-' : '+';
  toggleEl.dataset.expanded = expanded ? '1' : '0';
}

function toggleExpanded(childrenEl, toggleEl){
  const expanded = toggleEl.dataset.expanded === '1';
  setExpanded(childrenEl, toggleEl, !expanded);
}

export function renderTree(elTree, onSelectionChanged){
  elTree.innerHTML = '';
  for (const id of state.rootIds){
    elTree.appendChild(renderNode(id, onSelectionChanged));
  }
}

function renderNode(id, onSelectionChanged){
  const p = state.pagesById.get(id);

  const wrap = document.createElement('div');
  const row = document.createElement('div');
  row.className = 'node';

  const hasChildren = (p.children && p.children.length > 0);

  const toggle = document.createElement('div');
  toggle.className = 'toggle' + (hasChildren ? '' : ' disabled');
  toggle.textContent = hasChildren ? '+' : '•';
  toggle.dataset.expanded = '0';

  const cb = document.createElement('input');
  cb.type = 'checkbox';
  cb.className = 'checkbox';
  cb.checked = state.selected.has(p.id);

  const label = document.createElement('div');
  label.className = 'label';

  // Title only (no slug/id line). Tooltip shows full title.
  const titleText = (p.title || '(untitled)');
  label.innerHTML = `<div class="t" title="${esc(titleText)}">${esc(titleText)}</div>`;

  const children = document.createElement('div');
  children.className = 'children hidden';

  if (hasChildren){
    for (const cid of p.children){
      children.appendChild(renderNode(cid, onSelectionChanged));
    }

    // Clicking the plus toggles
    toggle.onclick = (e) => {
      e.stopPropagation();
      toggleExpanded(children, toggle);
    };

    // Clicking anywhere on the row except checkbox toggles (same as plus)
    row.onclick = (e) => {
      if (isInteractiveTarget(e.target)) return;
      toggleExpanded(children, toggle);
    };
  } else {
    // Still allow row click to do nothing for leaf nodes.
    row.onclick = (e) => {};
  }

  cb.onchange = () => {
    if (cb.checked){
      state.selected.set(p.id, {
        space_id: p.space_id,
        page_id: p.id,
        title: p.title || '',
        slug_id: p.slug_id || '',
      });
    } else {
      state.selected.delete(p.id);
    }
    onSelectionChanged();
  };

  row.appendChild(toggle);
  row.appendChild(cb);
  row.appendChild(label);
  wrap.appendChild(row);
  wrap.appendChild(children);

  return wrap;
}
