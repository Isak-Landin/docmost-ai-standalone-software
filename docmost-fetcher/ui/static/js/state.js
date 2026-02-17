export const state = {
  currentSpace: null,         // {id,name,slug}
  pagesById: new Map(),       // id -> page {children:[]}
  rootIds: [],                // top-level page ids
  selected: new Map(),        // page_id -> {space_id,page_id,title,slug_id}
};

export function clearSelection(){
  state.selected.clear();
}

export function setSpace(space){
  state.currentSpace = space;
  clearSelection();
}
