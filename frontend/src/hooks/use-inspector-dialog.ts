import {useEffect,useRef,useState} from "react";

/** The inspector is inline on desktop and a dismissible modal on narrow screens. */
export function useInspectorDialog(open:boolean,onClose:()=>void){
  const element=useRef<HTMLElement>(null);
  const [narrow,setNarrow]=useState(()=>window.matchMedia?.("(max-width:1100px)").matches??false);
  useEffect(()=>{
    if(!window.matchMedia)return;
    const media=window.matchMedia("(max-width:1100px)");
    const sync=()=>setNarrow(media.matches);sync();media.addEventListener("change",sync);
    return()=>media.removeEventListener("change",sync);
  },[]);
  const modal=open&&narrow;
  useEffect(()=>{
    if(!modal)return;
    const focused=document.activeElement instanceof HTMLElement?document.activeElement:null;
    const overflow=document.body.style.overflow;document.body.style.overflow="hidden";
    element.current?.querySelector<HTMLElement>("button")?.focus();
    const keydown=(event:KeyboardEvent)=>{
      if(event.key==="Escape"){event.preventDefault();event.stopPropagation();onClose();}
      if(event.key!=="Tab")return;
      const items=[...(element.current?.querySelectorAll<HTMLElement>('button,a[href],input,select,textarea,[tabindex="0"]')??[])].filter(item=>!item.hasAttribute("disabled")&&item.getClientRects().length);
      if(event.shiftKey&&document.activeElement===items[0]){event.preventDefault();items.at(-1)?.focus();}
      if(!event.shiftKey&&document.activeElement===items.at(-1)){event.preventDefault();items[0]?.focus();}
    };
    window.addEventListener("keydown",keydown);
    return()=>{document.body.style.overflow=overflow;window.removeEventListener("keydown",keydown);if(focused?.isConnected)focused.focus();};
  },[modal,onClose]);
  return {element,modal};
}
