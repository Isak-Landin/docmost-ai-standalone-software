import { esc } from './util.js';
import { state } from './state.js';
import { postChat } from './api.js';

export function addChat(elChat, who, text){
  const div = document.createElement('div');
  div.className = 'msg';
  div.innerHTML = `<div class="who">${esc(who)}</div><div>${esc(text).replace(/\n/g,'<br>')}</div>`;
  elChat.appendChild(div);
  elChat.scrollTop = elChat.scrollHeight;
}

export async function sendChat(elChat, message){
  const payload = {
    space: state.currentSpace,
    selected_pages: Array.from(state.selected.values()),
    message,
  };

  const data = await postChat(payload);
  addChat(elChat, 'assistant', data.reply ?? JSON.stringify(data));
}
