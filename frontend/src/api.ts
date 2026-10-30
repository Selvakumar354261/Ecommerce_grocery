let csrf='';
export function setCsrf(value:string){csrf=value;}
export class ApiError extends Error {constructor(public status:number,message:string){super(message);}}
export async function api<T>(path:string,options:RequestInit={}):Promise<T>{
  const response=await fetch('/api/v1'+path,{...options,credentials:'same-origin',headers:{'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':csrf}:{}),...options.headers}});
  const data=await response.json().catch(()=>({detail:'The server returned an unexpected response.'}));
  if(!response.ok)throw new ApiError(response.status,typeof data.detail==='string'?data.detail+(data.fields?' '+data.fields.join(' '):''):'Please check the submitted information.');
  return data as T;
}
export async function post<T>(path:string,data:unknown={},requestKey?:string):Promise<T>{
  const body=JSON.stringify(data);
  let pending='',effectiveKey=requestKey;
  if(requestKey){
    const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(path+'\n'+body));
    pending='grove.pending.'+Array.from(new Uint8Array(hash)).map(x=>x.toString(16).padStart(2,'0')).join('');
    try{effectiveKey=sessionStorage.getItem(pending)||requestKey;sessionStorage.setItem(pending,effectiveKey)}catch{/* Retry key still remains in component state. */}
  }
  try{
    const result=await api<T>(path,{method:'POST',body,headers:effectiveKey?{'Idempotency-Key':effectiveKey}:{}});
    if(pending)try{sessionStorage.removeItem(pending)}catch{/* Storage may be restricted. */}
    return result;
  }catch(error){
    if(pending&&error instanceof ApiError&&[400,409,422].includes(error.status))try{sessionStorage.removeItem(pending)}catch{/* Storage may be restricted. */}
    throw error;
  }
}
export async function upload<T>(path:string,file:File):Promise<T>{
  const response=await fetch('/api/v1'+path,{method:'POST',body:file,credentials:'same-origin',headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',...(csrf?{'X-CSRF-Token':csrf}:{})}});
  const data=await response.json().catch(()=>({detail:'The server returned an unexpected response.'}));
  if(!response.ok)throw new ApiError(response.status,typeof data.detail==='string'?data.detail:'Please check the uploaded workbook.');
  return data as T;
}
export const key=()=>crypto.randomUUID();
export const money=(x:number|string)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(Number(x));
export const quantity=(x:number|string)=>Number(x).toLocaleString('en-IN',{maximumFractionDigits:3});
export const amount=(price:number|string,qty:number)=>Math.round(Math.round(Number(price)*100)*Math.round(qty*1000)/1000)/100;
export const date=(x:string)=>new Date(x).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'});
