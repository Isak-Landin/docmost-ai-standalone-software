import { fetchSpaces, fetchPages } from './api.js';
import { state, setSpace, clearSelection } from './state.js';
import { buildTree, renderTree } from './tree.js';
import { addChat, sendChat } from './chat.js';

const elSpaces = document.getElementById('spaces');
const elTree = document.getElementById('tree');
const elSpaceTitle = document.getElementById('spaceTitle');
const elChat = document.getElementById('chat');
const elMsg = document.getElementById('msg');
const btnSend = document.getElementById('sendBtn');
const btnCopy = document.getElementById('copyBtn');
const btnClear = document.getElementById('clearBtn');
const elSelectedCount = document.getElementById('selectedCount');

function setStateUI(){
  const hasSpace = !!state.currentSpace;
  const hasSel = state.selected.size > 0;

  btnSend.disabled = !hasSpace;
  btnCopy.disabled = !hasSpace || !hasSel;
  btnClear.disabled = !hasSpace || !hasSel;

  elSelectedCount.textContent = String(state.selected.size);
}

async function loadSpacesUI(){
  const spaces = await fetchSpaces();
  elSpaces.innerHTML = '';

  for (const sp of spaces){
    const div = document.createElement('div');
    div.className = 'space';
    div.innerHTML = `<div class="name">${(sp.name || '(unnamed)')}</div><div class="id">${sp.id}</div>`;
    div.onclick = () => selectSpace(sp);
    elSpaces.appendChild(div);
  }
}

async function selectSpace(space){
  setSpace(space);
  setStateUI();

  elSpaceTitle.textContent = space.name || '(unnamed)';
  elChat.innerHTML = '';
  addChat(elChat, 'system', `Space selected: ${space.name || '(unnamed)'} (${space.id})`);

  const pages = await fetchPages(space.id);
  buildTree(pages);
  renderTree(elTree, setStateUI);

  setStateUI();
}

btnClear.onclick = () => {
  clearSelection();
  renderTree(elTree, setStateUI);
  setStateUI();
};

btnCopy.onclick = async () => {
  const payload = { space: state.currentSpace, selected_pages: Array.from(state.selected.values()) };
  await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
  addChat(elChat, 'system', 'Copied selection JSON to clipboard.');
};

async function handleSend(){
  const txt = (elMsg.value || '').trim();
  if (!txt || !state.currentSpace) return;

  addChat(elChat, 'user', txt);
  elMsg.value = '';

  try {
    await sendChat(elChat, txt);
  } catch (e) {
    addChat(elChat, 'system', String(e?.message || e));
  }
}

btnSend.onclick = handleSend;

elMsg.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey){
    e.preventDefault();
    handleSend();
  }
});

(async function init(){
  setStateUI();
  await loadSpacesUI();
})();
