import { useState } from "react";

import { Button } from "@/components/ui/button";

type ApiStatus = "não verificada" | "verificando" | "pronta" | "indisponível";

export function App() {
  const [status, setStatus] = useState<ApiStatus>("não verificada");

  async function checkApi() {
    setStatus("verificando");
    try {
      const resp = await fetch("/api/ready");
      setStatus(resp.ok ? "pronta" : "indisponível");
    } catch {
      setStatus("indisponível");
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold">Telemetria de frota</h1>
      <p className="text-muted-foreground">Esqueleto da etapa 1. As telas chegam nas etapas 12 e 13.</p>
      <div className="flex items-center gap-3">
        <Button onClick={checkApi}>Verificar API</Button>
        <span aria-live="polite">API: {status}</span>
      </div>
    </main>
  );
}
