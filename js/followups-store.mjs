import * as C from './followups-core.mjs';
export function makeFollowupStore(db,storage){
  const col=db.collection('record_followups'),reviews=db.collection('record_followup_reviews');
  const rows=s=>s.docs.map(d=>({...d.data(),id:d.id}));
  return {
    newId:()=>col.doc().id,
    read:async id=>{const s=await col.doc(id).get({source:'server'});return s.exists?{id:s.id,...s.data()}:null;},
    all:async()=>rows(await col.get({source:'server'})),
    history:async id=>rows(await reviews.where('followupId','==',id).get({source:'server'})).sort((a,b)=>(b.recordedAt||0)-(a.recordedAt||0)),
    // 전체 기간 완료 표식을 읽고 원본 질문·완료 표식을 보존한다. 기존 문서는 변경하지 않는다.
    async migrate(records,needsReview){
      const old=rows(await db.collection('records_todos').get({source:'server'}));
      const candidates=await C.legacyItems(records,old,needsReview);let created=0;
      for(const item of candidates){
        const ref=col.doc(item.id);
        await db.runTransaction(async tx=>{const s=await tx.get(ref);if(s.exists)return;
          const now=Date.now(),data={...item,createdAt:now,updatedAt:now,revision:1,migrationVersion:1};
          tx.set(ref,data);tx.set(reviews.doc(item.id+'_migration'),{...data,followupId:item.id,event:'migrated',recordedAt:now});created++;
        });
      }
      return {candidates:candidates.length,created,oldMarkers:old.length};
    },
    async save(id,patch,expected,operationId){
      return db.runTransaction(async tx=>{
        const ref=col.doc(id),snap=await tx.get(ref);
        const result=C.saveTransition(snap.exists?snap.data():null,patch,{expected,operationId,id});
        if(!result.repeated){tx.set(ref,result.item);tx.set(reviews.doc(id+'_'+operationId),{...result.review,followupId:id});}
        return result.item;
      });
    },
    async upload(file){
      if(!storage)throw Error('STORAGE_UNAVAILABLE');if(!/^image\/(png|jpeg|gif|webp|avif|bmp)$/.test(file.type))throw Error('IMAGE_TYPE');if(file.size>8*1024*1024)throw Error('IMAGE_SIZE');
      const id=crypto.randomUUID(),path='records_images/'+C.day(Date.now())+'/followup_'+id;
      const s=await storage.ref(path).put(file,{contentType:file.type});
      return {id,path,url:await s.ref.getDownloadURL(),name:file.name||'',type:file.type,size:file.size};
    },
    async restoreItem(item,history,operation){
      return db.runTransaction(async tx=>{const ref=col.doc(item.id),s=await tx.get(ref);if(s.exists){if(s.data().restoreOperation===operation)return;throw Error('RESTORE_CONFLICT');}
        if(history.length>400)throw Error('TOO_MANY_REVIEWS');
        tx.set(ref,{...item,restoreOperation:operation});
        history.forEach((r,i)=>tx.set(reviews.doc(item.id+'_restore_'+i),{...r,followupId:item.id}));
      });
    }
  };
}
