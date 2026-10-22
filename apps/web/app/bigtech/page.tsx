// Big tech lives in the Discover station now (it is part of discovery, not the control room).
import { redirect } from "next/navigation";

export default function BigTechPage() {
  redirect("/room/listen#bigtech");
}
