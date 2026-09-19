/* Local synthetic harness only. No Firebase SDK or network persistence. */
(function () {
  const rows = new Map();
  window.__localWrites = [];
  function snap(id, data) { return {id, exists: data !== undefined, data: () => data}; }
  function collection(name, filters = []) {
    return {
      where: (...f) => collection(name, [...filters, f]),
      orderBy: () => collection(name, filters), limit: () => collection(name, filters),
      get: async () => {
        const docs = [...rows].filter(([k,v]) => k.startsWith(name+'/') && filters.every(([f,op,x]) => op !== '==' || v[f] === x))
          .map(([k,v]) => snap(k.slice(name.length+1), v));
        return {docs, empty: !docs.length, size: docs.length, forEach: fn => docs.forEach(fn)};
      },
      doc: id => ({
        get: async () => snap(id, rows.get(name+'/'+id)),
        set: async (value, opts) => {
          rows.set(name+'/'+id, opts && opts.merge ? {...rows.get(name+'/'+id), ...value} : value);
          window.__localWrites.push({name,id,value});
        },
        update: async value => {
          rows.set(name+'/'+id, {...rows.get(name+'/'+id), ...value});
          window.__localWrites.push({name,id,value});
        },
        delete: async () => rows.delete(name+'/'+id)
      })
    };
  }
  const firestore = () => ({collection});
  firestore.FieldValue = {increment: n => n, arrayUnion: (...x) => x};
  window.firebase = {initializeApp: () => {}, firestore, auth: () => ({
    signInAnonymously: async () => ({user:{uid:'LOCAL-SYNTHETIC'}}),
    onAuthStateChanged: fn => setTimeout(() => fn({uid:'LOCAL-SYNTHETIC'}), 0)
  })};
})();
