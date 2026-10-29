import {render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {describe,expect,it} from "vitest";
import {MemoryRouter,useLocation,useNavigate} from "react-router-dom";
import {useResourceSelection} from "../../hooks/use-resource-selection";
import {ResourcePicker} from "./resource-picker";

function Reader(){
  const [value,select]=useResourceSelection("run_id");const location=useLocation(),navigate=useNavigate();
  return <><ResourcePicker value={value} onSelect={select} kind="run"/><output aria-label="当前地址">{location.search}</output><button onClick={()=>navigate(-1)}>后退</button></>;
}
describe("explicit record selection",()=>{
  it("restores IDs from browser history and clears instead of falling back to a sample",async()=>{
    const user=userEvent.setup();render(<MemoryRouter><Reader/></MemoryRouter>);
    expect(screen.getByRole("button",{name:"载入记录"})).toBeDisabled();
    const input=screen.getByLabelText("调查运行 ID");
    await user.type(input,"run-real-first");await user.click(screen.getByRole("button",{name:"载入记录"}));
    expect(screen.getByLabelText("当前地址")).toHaveTextContent("run_id=run-real-first");
    await user.clear(input);await user.type(input,"run-real-second");await user.click(screen.getByRole("button",{name:"载入记录"}));
    await user.click(screen.getByRole("button",{name:"后退"}));await waitFor(()=>expect(input).toHaveValue("run-real-first"));
    await user.click(screen.getByRole("button",{name:"清除选择"}));expect(input).toHaveValue("");expect(screen.getByText(/尚未选择调查运行 ID/)).toBeInTheDocument();
  });
});
