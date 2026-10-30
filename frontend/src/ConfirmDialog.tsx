import {createContext,useContext,useRef,useState} from 'react';
import {Button,Dialog,DialogActions,DialogContent,DialogTitle,Typography} from '@mui/material';

type Confirmation={title:string;message:string;confirmLabel:string;danger:boolean};
type Ask=(message:string,options?:{title?:string;confirmLabel?:string;danger?:boolean})=>Promise<boolean>;
const ConfirmContext=createContext<Ask|null>(null);

export function ConfirmationProvider({children}:{children:React.ReactNode}){
 const [request,setRequest]=useState<Confirmation|null>(null);
 const resolver=useRef<((answer:boolean)=>void)|null>(null);
 function ask(message:string,options?:{title?:string;confirmLabel?:string;danger?:boolean}){
  resolver.current?.(false);
  setRequest({title:options?.title||'Please confirm',message,confirmLabel:options?.confirmLabel||'Confirm',danger:options?.danger||false});
  return new Promise<boolean>(resolve=>{resolver.current=resolve});
 }
 function close(answer:boolean){resolver.current?.(answer);resolver.current=null;setRequest(null)}
 return <ConfirmContext.Provider value={ask}>{children}<Dialog open={!!request} onClose={()=>close(false)} fullWidth maxWidth="xs"><DialogTitle>{request?.title}</DialogTitle><DialogContent><Typography>{request?.message}</Typography></DialogContent><DialogActions><Button onClick={()=>close(false)}>Cancel</Button><Button autoFocus variant="contained" color={request?.danger?'error':'primary'} onClick={()=>close(true)}>{request?.confirmLabel}</Button></DialogActions></Dialog></ConfirmContext.Provider>;
}

export function useConfirmDialog(){
 const ask=useContext(ConfirmContext);
 if(!ask)throw new Error('ConfirmationProvider is missing.');
 return {ask,confirmationDialog:null};
}
