import {Link, Navigate, useLocation} from "react-router-dom";

export function HomeRedirect() {
  const location=useLocation();return <Navigate to={{pathname:"/sandbox",search:location.search}} replace/>;
}
export function NotFoundPage() {
  return <section className="resource-empty"><h1 className="text-xl font-semibold">页面不存在</h1><p className="my-3">链接可能已失效，请从工作区导航继续。</p><Link to="/sandbox">返回总控台</Link></section>;
}
export function WorkspaceErrorPanel() {
  return <section className="resource-empty" role="alert"><h1 className="text-xl font-semibold">页面暂时无法显示</h1><p className="my-3">请刷新页面后重试，或从工作区导航继续。已有实验不会因此重新执行。</p><button className="quiet-button" onClick={()=>window.location.reload()}>刷新页面</button><Link className="quiet-button" to="/sandbox">返回总控台</Link></section>;
}
