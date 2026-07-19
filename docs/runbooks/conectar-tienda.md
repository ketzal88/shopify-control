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

Arrancá Claude desde la carpeta del cliente (`cd clients/{slug}` y abrí Claude ahí), y pedile en lenguaje normal:

1. **Read:** "¿Qué productos hay en la tienda?" → debería responder leyendo la tienda.
2. **Write con gate:** "Mejorá la descripción de [un producto de demo]" → debería mostrarte el **preview antes/después** y pedirte **sí/no**. Decí que sí.
3. **Verificar el backup:** revisá que quedó un archivo nuevo en `clients/{slug}/backups/` y una entrada en `worklog.md`.
4. **Undo:** pedí "volvé a la anterior" → la descripción debería volver como estaba.
5. **Bloqueo:** (opcional, para confiar en la red) borrá el backup a mano e intentá forzar un cambio → el hook lo debería frenar.

Si los 5 pasos dan bien, la herramienta está lista para la tienda real del cliente.

---

## Notas técnicas (para la calibración, Task 7 del plan)

Una vez conectada la tienda, hay que ajustar el hook al connector real:

- Inspeccionar el **nombre exacto del tool de escritura** del connector y la forma de su payload; ajustar `WRITE_TOOL_MARKERS` / `WRITE_ACTION_MARKERS` / `_write_target()` en `.claude/hooks/backup_guard.py`.
- El Admin API usa `descriptionHtml` (descripción) y los metafields `global.title_tag` / `global.description_tag` (SEO), **no** `meta_title` plano. Mover en lockstep: el skill `mejorar-descripcion` (paso 9), el hook, y `store-standards §8`.
- Verificar el mecanismo de bloqueo del hook (exit 2 vs JSON `permissionDecision`) contra la doc de hooks de Claude Code.
