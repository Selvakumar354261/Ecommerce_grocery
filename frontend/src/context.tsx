import {createContext,useContext} from 'react';
import type {User,CartLine,Product} from './types';
export type AppContextValue={user:User|null;authLoading:boolean;refreshAuth:()=>Promise<void>;signOut:()=>Promise<void>;cart:CartLine[];setCart:(items:CartLine[])=>void;add:(id:number,qty:number)=>void;catalogue:Product[];notify:(message:string)=>void};
export const AppContext=createContext<AppContextValue>(null!);
export const useApp=()=>useContext(AppContext);
