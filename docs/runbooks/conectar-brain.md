# Cómo conectar el Brain (solo lectura) a shopify-control

> Para Gabriel / equipo Worker. Enchufa los datos de marketing del cliente que vive en Worker
> Brain (ventas, alertas, SEO, performance de creativos, inteligencia de compradores) para que
> Claude los use al mejorar la tienda. Es **solo lectura** y **solo de ese cliente** — lo
> garantiza el server del Brain, no la buena fe.

Esto es el "input del Brain" que el spec del v1 dejaba como placeholder (§10, §13, roadmap
W1.5). Ya tiene un camino seguro para el hand-off al cliente: **no hace falta ningún MCP custom,
ningún puente, ni ningún token embebido en el repo.**

---

## Qué es (y qué NO es)

- **Es** el connector **"Worker Brain"** de Claude, igual que el de Shopify: se agrega en los
  ajustes de Claude y se autentica con Google (OAuth). No es un server dentro del repo, **no va
  en `.mcp.json`**, y **no lleva ningún token en el repo**.
- Da acceso de **solo lectura** a los datos de **un** cliente: el que corresponde al email con
  el que te logueás. No escribe nada en el Brain, ni ve otros clientes.
- El scoping vive en el server del Brain (`/api/mcp-server`): aunque exista más, a un cliente
  solo le habilita **sus** lecturas — nada de consultas libres, nada de cartera cruzada, nada
  de mutaciones. Ni siquiera aparecen en la lista de herramientas.

---

## Parte A: Requisito previo (una vez, lo hace el operador)

El email de Google con el que se van a loguear tiene que estar en el perfil del cliente en el
Brain (campo `allowedEmails`). Es el **mismo** que le da acceso al portal — no es una lista
aparte.

- **blunua** ya lo tiene: `lauramorenoperez.b@gmail.com` y `elisaescobar11@gmail.com`.
- Si un cliente no está, se agrega desde el admin del Brain (perfil del cliente). Sin Vercel,
  sin deploy.

---

## Parte B: Agregar el connector en Claude

1. En **Claude** (app de escritorio o claude.ai) → **Settings → Connectors** (Configuración →
   Conectores) — el mismo lugar donde agregaste el de Shopify.
2. **Add custom connector** (Agregar conector personalizado).
3. Pegá la URL del server:  `https://brain.worker.ar/api/mcp-server`
4. Te manda a loguear con **Google**. Usá el email del cliente (el de la Parte A).
5. Aprobá. El connector "Worker Brain" queda disponible dentro de Claude Code, scopeado a ese
   cliente y de solo lectura.

> ⚠️ **Quién se loguea define qué ve.** Con tu `@worker.ar` ves TODA la cartera (sos operador);
> con el email del cliente ves solo lo suyo. Para el hand-off al cliente, **siempre** con el
> email del cliente.

> 🧪 Es una superficie nueva de verdad: probá la primera conexión externa (blunua) de punta a
> punta antes de prometerla. El login externo real por claude.ai todavía no se ejerció; el gate
> y el scoping sí están verificados del lado del server.

---

## Parte C: Para qué sirve (los datos útiles)

Durante el **refresh trimestral** (§8.1 del spec), o cuando quieras enriquecer una descripción
o un combo con evidencia real, estos son los tools de solo lectura que aportan:

- `get_seo_gaps` — keywords donde rankeás orgánico sin pauta / pagás sin orgánico (GSC × Google Ads).
- `get_creative_intelligence` — qué ángulos y mensajes ganan en los ads (insumo para el copy).
- `get_customer_intelligence` — quién compra, LTV, tasa de recompra, fuente de adquisición.
- `get_channel_metrics` (GA4 / GSC / ECOMMERCE) — cómo se vende y qué busca la gente.
- `get_client_brief` — el retrato completo del cliente en una sola llamada.

Las reglas de escritura siguen en `store-standards.md`; el Brain solo aporta la evidencia.

---

## Notas

- **Nada sensible en el repo.** El acceso es OAuth por-usuario: no se embebe ningún token, el
  `.mcp.json` queda vacío a propósito. (Distinto del puente interno de Worker, que sí usa un
  token compartido de acceso total — ese **nunca** va en este repo.)
- Si algún día el cliente opera esto solo (roadmap D2, hand-off empaquetado), este mismo camino
  ya es seguro por construcción: cada uno ve únicamente su tienda y sus propios números.
