import { redirect } from "next/navigation";
import { readSession } from "./_lib/session";

export default async function Home() {
  redirect(await readSession() ? "/dashboard" : "/login");
}
