import {useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {Alert,Button,MenuItem,Stack,TextField,Typography} from '@mui/material';
import {api,post} from './api';
import {useConfirmDialog} from './ConfirmDialog';

type SavedAddress={id:number;label:string;address:string;phone:string|null;latitude:string;longitude:string};
export default function SavedAddresses({userId,address,phone,lat,lon,onSelect}:{userId:number;address:string;phone:string;lat:string;lon:string;onSelect:(address:string,phone:string,lat:string,lon:string)=>void}) {
  const qc=useQueryClient(), confirmation=useConfirmDialog();
  const [selected,setSelected]=useState(0),[label,setLabel]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const query=useQuery({queryKey:['saved-addresses',userId],queryFn:()=>api<SavedAddress[]>('/customer/addresses')});
  const chosen=query.data?.find(a=>a.id===selected);
  async function save(update:boolean) {
    setBusy(true);setError('');
    try {
      const body={label,address,phone,latitude:lat,longitude:lon};
      const saved=update ? await api<SavedAddress>(`/customer/addresses/${selected}`,{method:'PUT',body:JSON.stringify(body)}) : await post<SavedAddress>('/customer/addresses',body);
      setSelected(saved.id);await qc.invalidateQueries({queryKey:['saved-addresses',userId]});
    } catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  async function remove() {
    if(!chosen || !await confirmation.ask(`Remove ${chosen.label} from your saved addresses?`,{title:'Remove saved address',confirmLabel:'Remove',danger:true})) return;
    setBusy(true);setError('');
    try {await api(`/customer/addresses/${selected}`,{method:'DELETE'});setSelected(0);setLabel('');await qc.invalidateQueries({queryKey:['saved-addresses',userId]});}
    catch(e){setError((e as Error).message);} finally{setBusy(false);}
  }
  return <Stack spacing={1.5}>
    <Typography variant="subtitle2">Saved delivery details</Typography>
    <TextField select label="Choose a saved address" value={chosen ? selected : 0} disabled={busy} onChange={e=>{
      const id=Number(e.target.value), saved=query.data?.find(a=>a.id===id);setSelected(id);setLabel(saved?.label || '');
      if(saved) onSelect(saved.address,saved.phone || '',saved.latitude,saved.longitude);
    }}>
      <MenuItem value={0}>New / unsaved location</MenuItem>
      {query.data?.map(a=><MenuItem key={a.id} value={a.id}>{a.label} — {a.address} · {a.phone || 'Add contact mobile'}</MenuItem>)}
    </TextField>
    <TextField label="Location name (e.g. Home, Work, Farm)" value={label} disabled={busy} inputProps={{maxLength:80}} onChange={e=>setLabel(e.target.value)}/>
    <Typography variant="caption">Each option saves the address, contact mobile, latitude and longitude together. Fill in all four below, then save.</Typography>
    <Stack direction="row" spacing={1} flexWrap="wrap">
      <Button disabled={busy} onClick={()=>void save(false)}>Save as new location</Button>
      {chosen && <><Button disabled={busy} onClick={()=>void save(true)}>Update saved location</Button><Button color="error" disabled={busy} onClick={()=>void remove()}>Remove</Button></>}
    </Stack>
    {(error || query.isError) && <Alert severity="error">{error || query.error?.message}</Alert>}
  </Stack>;
}
