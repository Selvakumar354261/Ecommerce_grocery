import {useEffect,useState} from 'react';
import {Link,Navigate,Route,Routes,useLocation,useNavigate} from 'react-router-dom';
import {Alert,AppBar,Box,Button,CircularProgress,Container,MenuItem,Paper,Snackbar,Stack,TextField,Toolbar,Typography} from '@mui/material';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import ShoppingBagOutlined from '@mui/icons-material/ShoppingBagOutlined';
import SpaOutlined from '@mui/icons-material/SpaOutlined';
import {api,post,setCsrf} from './api';
import {AppContext,useApp} from './context';
import type {CartLine,Product,User} from './types';
import {Shop,Checkout,CustomerOrders} from './Shop';
import {Operations} from './Operations';

function Header(){
 const {user,signOut,cart}=useApp();
 const location=useLocation();
 const portalLogin=location.pathname==='/portal/login';
 const staff=!!user?.permissions.includes('workspace');
 return <AppBar position="sticky" color="inherit" elevation={0} className="topbar"><Container maxWidth="xl"><Toolbar disableGutters sx={{gap:2,minHeight:76}}>
  <Link to={staff?'/workspace':portalLogin?'/portal/login':'/'} className="brand" aria-label="CHINNU home"><img src="/chinnu-logo.jpeg" alt="CHINNU" className="brand-logo"/></Link>
  <Box sx={{flex:1}}/>
  {!portalLogin&&<Box className="header-actions">
  {!staff&&<Button component={Link} to="/" color="inherit">Shop</Button>}
  {!staff&&<Button component={Link} to="/#branches" color="inherit">Branches</Button>}
  {user?.permissions.includes('orders.self')&&<Button component={Link} to="/orders" color="inherit">My orders</Button>}
  {staff&&<Button component={Link} to="/workspace">Workspace</Button>}
  {!staff&&<Button component={Link} to="/checkout" startIcon={<ShoppingBagOutlined/>} variant="outlined">Cart ({cart.length})</Button>}
  {user?<Button onClick={()=>void signOut()}>Sign out</Button>:<Button component={Link} to="/login" variant="contained">Sign in</Button>}
  </Box>}
 </Toolbar></Container></AppBar>
}

function Login(){
 const [email,setEmail]=useState(''),[name,setName]=useState(''),[phone,setPhone]=useState(''),[otp,setOtp]=useState(''),[otpSent,setOtpSent]=useState(false),[needsProfile,setNeedsProfile]=useState(false),[developmentOtp,setDevelopmentOtp]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const {refreshAuth}=useApp();const navigate=useNavigate();
 async function submit(e:React.FormEvent){e.preventDefault();setError('');setBusy(true);try{
  if(!otpSent){const result=await post<{sent:boolean;development_otp?:string}>('/auth/otp/request',{phone});setOtpSent(true);setDevelopmentOtp(result.development_otp||'');return}
  const result=await post<{user?:User;csrf?:string;profile_required?:boolean}>('/auth/otp/verify',{phone,otp,name:needsProfile?name.trim()||null:null,email:needsProfile?email.trim()||null:null});
  if(result.profile_required){setNeedsProfile(true);setError('');return}
  setCsrf(result.csrf!);await refreshAuth();navigate('/');
 }catch(err){setError((err as Error).message)}finally{setBusy(false)}}
 return <Container maxWidth="lg" sx={{py:7}}><div className="auth-grid"><div className="auth-story"><span className="eyebrow">CHINNU</span><h1>Pure grains.<br/>Better tomorrow.</h1><p>Modern rice mill, cattle feed, and everyday essentials from CHINNU.</p><div className="auth-leaf"><SpaOutlined sx={{fontSize:130}}/></div></div><Paper variant="outlined" sx={{p:{xs:3,md:5},borderRadius:4}}><Typography variant="h4" gutterBottom>{needsProfile?'Create your account':otpSent?'Enter your OTP':'Continue with mobile'}</Typography><Typography color="text.secondary" sx={{mb:3}}>{needsProfile?'We verified your number. Tell us your name once to finish.':otpSent?`We sent a six-digit code to ${phone}.`:'No password needed.'}</Typography><Box component="form" onSubmit={submit}><Stack spacing={2.5}>
 {error&&<Alert severity="error">{error}</Alert>}
 {needsProfile?<><TextField label="Full name" required autoFocus value={name} onChange={e=>setName(e.target.value)} autoComplete="name"/><TextField label="Email address (optional)" type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email"/></>:<><TextField label="Mobile number" required value={phone} disabled={otpSent} onChange={e=>setPhone(e.target.value.replace(/\D/g,'').slice(0,10))} inputProps={{inputMode:'numeric',pattern:'[6-9][0-9]{9}',maxLength:10}} helperText="Enter a 10-digit Indian mobile number."/>{otpSent&&<><TextField label="Six-digit OTP" required autoFocus value={otp} onChange={e=>setOtp(e.target.value.replace(/\D/g,'').slice(0,6))} inputProps={{inputMode:'numeric',pattern:'[0-9]{6}',maxLength:6}}/>{developmentOtp&&<Alert severity="info">Development OTP: <strong>{developmentOtp}</strong></Alert>}</>}</>}
 <Button type="submit" variant="contained" size="large" disabled={busy||(!otpSent&&!/^[6-9][0-9]{9}$/.test(phone))||(otpSent&&!needsProfile&&!/^[0-9]{6}$/.test(otp))||(needsProfile&&name.trim().length<2)}>{busy?'Please wait…':needsProfile?'Create account':otpSent?'Verify and continue':'Send OTP'}</Button>
 {otpSent&&!needsProfile&&<Button onClick={()=>{setOtpSent(false);setNeedsProfile(false);setOtp('');setName('');setEmail('');setDevelopmentOtp('');setError('')}}>Change mobile number</Button>}
 </Stack></Box></Paper></div></Container>
}

function StaffLogin(){
 const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const {refreshAuth}=useApp();const navigate=useNavigate();
 async function submit(e:React.FormEvent){e.preventDefault();setError('');setBusy(true);try{const result=await post<{user:User;csrf:string}>('/auth/login',{email,password});setCsrf(result.csrf);await refreshAuth();navigate('/workspace')}catch(err){setError((err as Error).message)}finally{setBusy(false)}}
 return <Container maxWidth="sm" sx={{py:{xs:5,md:9}}}><Paper variant="outlined" sx={{p:{xs:3,md:5},borderRadius:4}}><span className="eyebrow">CHINNU OPERATIONS</span><Typography variant="h4" sx={{mt:2}}>Admin &amp; staff portal</Typography><Typography color="text.secondary" sx={{mt:1,mb:3}}>Authorised team members only.</Typography><Box component="form" onSubmit={submit}><Stack spacing={2.5}>{error&&<Alert severity="error">{error}</Alert>}<TextField label="Staff email address" type="email" required value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email"/><TextField label="Password" type="password" required value={password} onChange={e=>setPassword(e.target.value)} inputProps={{maxLength:128}} autoComplete="current-password"/><Button type="submit" variant="contained" size="large" disabled={busy}>{busy?'Please wait…':'Open staff portal'}</Button></Stack></Box></Paper></Container>
}

export default function App(){
 const [user,setUser]=useState<User|null>(null),[authLoading,setLoading]=useState(true),[message,setMessage]=useState('');
 const [cart,setCartState]=useState<CartLine[]>(()=>{try{const saved=JSON.parse(localStorage.getItem('grove-cart')||'[]');return Array.isArray(saved)?saved.filter((x:CartLine)=>Number.isInteger(x.variant_id)&&Number(x.quantity)>0):[]}catch{return []}});
 const qc=useQueryClient();
 const catalogue=useQuery({queryKey:['catalogue'],queryFn:()=>api<Product[]>('/catalogue')});
 async function refreshAuth(){try{const r=await api<{user:User|null;csrf:string}>('/auth/session');setUser(r.user);setCsrf(r.csrf)}catch{setUser(null);setCsrf('')}finally{setLoading(false)}}
 useEffect(()=>{void refreshAuth()},[]);
 useEffect(()=>{localStorage.setItem('grove-cart',JSON.stringify(cart))},[cart]);
 function setCart(items:CartLine[]){setCartState(items.filter(x=>x.quantity>0));}
 function add(id:number,qty:number){setCartState(current=>{const old=current.find(x=>x.variant_id===id);return old?current.map(x=>x.variant_id===id?{...x,quantity:Number((x.quantity+qty).toFixed(3))}:x):[...current,{variant_id:id,quantity:qty}]});setMessage('Added to your cart');}
 async function signOut(){try{await post('/auth/logout');setUser(null);setCsrf('');qc.clear()}catch(err){setMessage((err as Error).message)}}
 return <AppContext.Provider value={{user,authLoading,refreshAuth,signOut,cart,setCart,add,catalogue:catalogue.data||[],notify:setMessage}}><Header/>
 {catalogue.isError&&<Container sx={{pt:2}}><Alert severity="error" action={<Button onClick={()=>void catalogue.refetch()}>Retry</Button>}>The catalogue could not load. Check that the backend is running.</Alert></Container>}
 <Routes><Route path="/" element={<Shop loading={catalogue.isPending}/>}/><Route path="/login" element={<Login/>}/><Route path="/portal/login" element={<StaffLogin/>}/><Route path="/checkout" element={<Checkout/>}/><Route path="/orders" element={authLoading?<Loading/>:user?.permissions.includes('orders.self')?<CustomerOrders/>:<Navigate to="/login"/>}/><Route path="/workspace/*" element={authLoading?<Loading/>:user?.permissions.includes('workspace')?<Operations/>:<Navigate to="/portal/login"/>}/><Route path="*" element={<Container sx={{py:8}}><Typography variant="h4">This page could not be found.</Typography><Button component={Link} to="/">Return to the shop</Button></Container>}/></Routes>
 <Snackbar open={!!message} autoHideDuration={4500} onClose={()=>setMessage('')} message={message}/>
 </AppContext.Provider>
}
export function Loading(){return <Box sx={{display:'flex',justifyContent:'center',py:8}}><CircularProgress aria-label="Loading"/></Box>}

