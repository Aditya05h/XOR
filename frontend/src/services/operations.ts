export async function request<T>(path:string, init:RequestInit={}):Promise<T> {
  const base=(import.meta.env.VITE_API_BASE_URL??'').replace(/\/$/,'')
  const response=await fetch(`${base}/api${path}`,{credentials:'include',...init,headers:{'Content-Type':'application/json',...init.headers}})
  if(!response.ok){ const body=await response.json().catch(()=>({detail:response.statusText})); throw new Error(typeof body.detail==='string'?body.detail:`Request failed (${response.status})`) }
  return response.json() as Promise<T>
}
export function post<T>(path:string,body:unknown={}):Promise<T>{return request(path,{method:'POST',body:JSON.stringify(body)})}
