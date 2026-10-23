import { cookies } from "next/headers";

export async function getServerToken(): Promise<string | null> {
  const store = await cookies();
  return store.get("stocklab_token")?.value ?? null;
}
