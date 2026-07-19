# Cómo conectar una tienda Shopify (paso a paso, sin saber programar)

> Para Gabriel / equipo Worker. Esta guía sirve tanto para una **tienda de prueba**
> (development store) como para la tienda real de un cliente. Recomendado: probar
> SIEMPRE primero en una tienda de prueba antes de tocar la del cliente.

---

## Parte A: Crear una tienda de prueba gratis (development store)

Una development store es una tienda Shopify completa, gratis y sin límite de tiempo, para probar sin riesgo.

1. Entrá a **partners.shopify.com** y creá una cuenta de **Shopify Partners** (es gratis; podés entrar con Google).
2. En el panel, andá a **"Stores"** (Tiendas) en el menú de la izquierda.
3. Clic en **"Add store"** → elegí **"Create development store"**.
4. Elegí el propósito (testing / uso interno), ponele un **nombre** y la **región**.
5. **IMPORTANTE:** marcá **"Start with test data"**. Así la tienda viene con **productos de demo** ya cargados, y podés probar sin subir nada a mano.
6. Crear. Ya tenés una tienda de prueba con productos.

Anotá el dominio que te queda: algo como `nombre.myshopify.com`.

---

## Parte B: Conectar esa tienda a Claude

1. En **Claude** (app de escritorio o claude.ai) andá a **Settings → Connectors** (Configuración → Conectores).
2. Buscá **"Shopify"** y dale **conectar / instalar** ("Shopify app for Claude").
3. Te redirige al **admin de Shopify** para autenticarte: logueate en la tienda de prueba.
4. Te muestra **qué permisos** le das a Claude. Para el v1 necesitás:
   - **Lectura y escritura de productos** (read/write products).
   - **Lectura de órdenes / analytics** (para los reportes).
5. **Aprobá.** Listo: Claude ya puede leer y escribir en esa tienda.

> ⚠️ No se puede **bajar** el nivel de permiso después sin desinstalar y volver a instalar.
> Podés **revocar** el acceso cuando quieras desde el admin de Shopify (Settings → Apps).

---

## Parte C: Dejar la tienda registrada en shopify-control

1. Abrí `clients/{slug}/connection.md` (ej: `clients/blunua/connection.md`) y completá:
   - **Store domain:** el `algo.myshopify.com`.
   - **Estado:** conectado (con la fecha).
2. Completá los `⚠️` de `clients/{slug}/store-standards.md`:
   - Vocabulario prohibido, keywords SEO por categoría, taxonomía de colecciones.

---

## Parte D: Probar que anda (en la tienda de PRUEBA)

Abrí **la RAÍZ del repo** (`shopify-control/`) en VS Code con la extensión de Claude Code.
Nunca abras `clients/{slug}/`: Claude Code busca `.claude/` en la carpeta que abrís, y ahí no
hay ninguna, así que la sesión queda **sin hooks y sin skills** mientras el connector de
Shopify igual puede escribir. `core/` y `stack.json` también viven en la raíz.

**Paso 0 (obligatorio):** desde la raíz no se auto-carga el `CLAUDE.md` del cliente. Antes de
operar, decile a Claude con qué cliente vas a trabajar y confirmá qué tienda está conectada
(ver Parte E). Recién después pedile en lenguaje normal:

1. **Read:** "¿Qué productos hay en la tienda?" → debería responder leyendo la tienda.
2. **Write con gate:** "Mejorá la descripción de [un producto de demo]" → debería mostrarte el **preview antes/después** y pedirte **sí/no**. Decí que sí.
3. **Verificar el backup:** revisá que quedó un archivo nuevo en `clients/{slug}/backups/` y una entrada en `worklog.md`.
4. **Undo:** pedí "volvé a la anterior" → la descripción debería volver como estaba.
5. **Bloqueo:** (opcional, para confiar en la red) borrá el backup a mano e intentá forzar un cambio → el hook lo debería frenar.

Si los 5 pasos dan bien, la herramienta está lista para la tienda real del cliente.

---

## Parte E: Verificar y cambiar la tienda activa

El connector puede tener **varias tiendas** conectadas a la vez (la de prueba y la del
cliente, por ejemplo), pero opera sobre **una sola a la vez**. Antes de cualquier write,
confirmá cuál está activa.

1. **Ver cuál está activa:** pedile a Claude "¿qué tienda está conectada?". Usa
   `Shopify:get-shop-info`, que devuelve el dominio `.myshopify.com`, el nombre, la moneda
   y el país de la tienda activa. Contrastalo con `clients/{slug}/connection.md`.
2. **Cambiar de tienda:** pedile "cambiá a la tienda `algo.myshopify.com`". Usa
   `Shopify:switch-shop`. Después volvé a correr el paso 1 para confirmar el cambio.
3. Si la tienda que querés **no aparece**, no está conectada todavía: repetí la Parte B
   autenticándote en esa tienda.

> ⚠️ Regla dura: nunca arranques un flujo de escritura sin haber confirmado la tienda
> activa en esta sesión. Si el dominio no coincide con el `connection.md` del cliente,
> frená y cambiá de tienda antes de seguir.

---

## Notas técnicas (estado real del v1)

Cómo está calibrado hoy el guardrail y qué campos se tocan de verdad:

- **Hook `.claude/hooks/backup_guard.py`** (matcher `.*`, `PreToolUse`): vigila los dos writes
  del flujo del skill. Reconoce la acción con `_action()`, que normaliza tanto el nombre real
  de MCP (`mcp__claude_ai_Shopify__update-product`) como el de display (`Shopify:update-product`);
  la lista en alcance es `GUARDED_PRODUCT_ACTIONS`. Para `graphql_mutation` mira la query
  (un `productUpdate` sobre un `gid://shopify/Product/...`). El producto sale de `_product_id()`.
  Si no hay backup reciente que cubra los 3 campos, **bloquea**.
- **Bloqueo verificado:** el mecanismo es **`exit 2`** (corta el tool y le muestra el stderr al
  modelo). Ya está confirmado en runtime en una sesión fresca de VS Code, ver `docs/HANDOFF.md`
  (PENDIENTE #1 y #1b). Un `exit 1` **no** bloquea: es un error no bloqueante y el tool corre igual.
- **Campos reales del v1:**
  - Descripción: `descriptionHtml`, se escribe con `Shopify:update-product`.
  - SEO: se **lee** con `graphql_query` sobre `product { seo { title description } }` y se
    **escribe** con `graphql_mutation` → `productUpdate(product: { id, seo: { title, description } })`.
    No se usan metafields `global.title_tag` / `global.description_tag`.
  - Ojo: el `input:` de `productUpdate` está deprecado; va `product:`.
- Si alguno de esos campos cambia, moverlo **en lockstep** en tres lugares: el skill
  `mejorar-descripcion`, el hook (`REQUIRED_BACKUP_FIELDS`) y `store-standards §8`.
