import {useEffect,useState} from 'react';
import {Link,Navigate,Route,Routes,useLocation,useNavigate} from 'react-router-dom';
import {Alert,AppBar,Box,Button,CircularProgress,Container,Paper,Snackbar,Stack,TextField,Toolbar,Typography} from '@mui/material';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {useRef} from 'react';
import {api,post,setCsrf} from './api';
import {AppContext,useApp} from './context';
import type {Product,User} from './types';
import {Operations} from './Operations';

// Admin-only web app: the customer shop, customer login and checkout have been removed.
function Header(){
 const headerRef=useRef<HTMLElement>(null);
 useEffect(()=>{
  const element=headerRef.current;
  if(!element)return;
  const update=()=>document.documentElement.style.setProperty('--app-header-height',`${element.getBoundingClientRect().height}px`);
  update();
  const observer=new ResizeObserver(update);observer.observe(element);
  return ()=>observer.disconnect();
 },[]);
 const {user,signOut}=useApp();
 const location=useLocation();
 const adminLogin=location.pathname==='/portal/login';
 const staff=!!user?.permissions.includes('workspace');
 return <AppBar ref={headerRef} position="sticky" color="inherit" elevation={0} className="topbar"><Container maxWidth="xl"><Toolbar disableGutters sx={{gap:2,minHeight:76}}>
  <Link to={staff?'/workspace':'/portal/login'} className="brand" aria-label="CHINNU home"><img src="/chinnu-logo-transparent.png" alt="CHINNU" className="brand-logo"/></Link>
  <Box sx={{flex:1}}/>
  {!adminLogin&&user&&<Box className="header-actions">
  {staff&&<Button component={Link} to="/workspace">Workspace</Button>}
  <Button onClick={()=>void signOut()}>Sign out</Button>
  </Box>}
 </Toolbar></Container></AppBar>
}

function AdminLogin(){
 const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const {refreshAuth}=useApp();const navigate=useNavigate();
 async function submit(e:React.FormEvent){e.preventDefault();setError('');setBusy(true);try{const result=await post<{user:User;csrf:string}>('/auth/login',{email,password});setCsrf(result.csrf);await refreshAuth();navigate('/workspace')}catch(err){setError((err as Error).message)}finally{setBusy(false)}}
 return <Container maxWidth="sm" sx={{py:{xs:5,md:9}}}><Paper variant="outlined" sx={{p:{xs:3,md:5},borderRadius:4}}><span className="eyebrow">CHINNU OPERATIONS</span><Typography variant="h4" sx={{mt:2}}>Admin login</Typography><Typography color="text.secondary" sx={{mt:1,mb:3}}>Administrators only.</Typography><Box component="form" onSubmit={submit}><Stack spacing={2.5}>{error&&<Alert severity="error">{error}</Alert>}<TextField label="Admin email address" type="email" required value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email"/><TextField label="Password" type="password" required value={password} onChange={e=>setPassword(e.target.value)} inputProps={{maxLength:128}} autoComplete="current-password"/><Button type="submit" variant="contained" size="large" fullWidth sx={{height:56}} disabled={busy}>{busy?'Please wait…':'Sign in'}</Button></Stack></Box></Paper></Container>
}

export default function App(){
 const [user,setUser]=useState<User|null>(null),[authLoading,setLoading]=useState(true),[message,setMessage]=useState('');
 const qc=useQueryClient();
 // The workspace still uses the product catalogue (POS, inventory), so it is loaded only after sign-in.
 const catalogue=useQuery({queryKey:['catalogue'],queryFn:()=>api<Product[]>('/catalogue'),enabled:!!user});
 async function refreshAuth(){try{const r=await api<{user:User|null;csrf:string}>('/auth/session');setUser(r.user);setCsrf(r.csrf)}catch{setUser(null);setCsrf('')}finally{setLoading(false)}}
 useEffect(()=>{void refreshAuth()},[]);
 async function signOut(){try{await post('/auth/logout');setUser(null);setCsrf('');qc.clear()}catch(err){setMessage((err as Error).message)}}
 const workspace=authLoading?<Loading/>:user?.permissions.includes('workspace')?<Operations/>:<Navigate to="/portal/login" replace/>;
 return <AppContext.Provider value={{user,authLoading,refreshAuth,signOut,catalogue:catalogue.data||[],notify:setMessage}}><Header/>
 {user&&catalogue.isError&&<Container sx={{pt:2}}><Alert severity="error" action={<Button onClick={()=>void catalogue.refetch()}>Retry</Button>}>The catalogue could not load. Check that the backend is running.</Alert></Container>}
 <Routes><Route path="/portal/login" element={<AdminLogin/>}/><Route path="/workspace/*" element={workspace}/><Route path="*" element={<Navigate to={user?'/workspace':'/portal/login'} replace/>}/></Routes>
 <Snackbar open={!!message} autoHideDuration={4500} onClose={()=>setMessage('')} message={message}/>
 </AppContext.Provider>
}
export function Loading(){return <Box sx={{display:'flex',justifyContent:'center',py:8}}><CircularProgress aria-label="Loading"/></Box>}
