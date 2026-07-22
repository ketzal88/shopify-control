---
name: poner-confianza
description: Pone señales de confianza en la tienda de Shopify — badges de cuotas, transferencia, envío gratis, garantía o seguridad; mensajes cortos; y el botón de WhatsApp. Aparecen en la ficha del producto o en toda la tienda. Muestra un preview en el chat, pide confirmación, guarda backup y permite sacarlos. Usar cuando el cliente pide mostrar cuotas, descuento por transferencia, envío gratis, un botón de WhatsApp, sellos de confianza o mensajes de garantía.
---

# Poner señales de confianza

Skill de **escritura** sobre la tienda viva. **No mueve plata** (es cosmético), pero es un write
igual, con el mismo protocolo duro que el resto: preview, gate, backup. Escribe el metafield
`worker.trust` (ítems tipados) que leen dos bloques de la tienda: los badges y mensajes van en la
ficha, y el WhatsApp es un botón flotante de toda la tienda.

Los badges de **cuotas** y **transferencia** son de los que más suben la conversión en Argentina y
Colombia; el botón de **WhatsApp** también. Por eso son el primer paquete.

## Reglas duras (no negociables)

- **Alcance:** solo escribir `worker.trust`. NUNCA precio, stock, status, tags, título, handle,
  colecciones ni ningún otro campo.
- **Tipos de ítem, set cerrado** (lo valida el guard, no lo fuerces):
  - `badge` → un **ícono** de `{cuotas, transferencia, envio, garantia, seguridad}` + un **texto**
    (hasta 40 caracteres). Nada de íconos ni imágenes propias.
  - `message` → un **texto** corto (hasta 80 caracteres).
  - `whatsapp` → un **teléfono** (solo dígitos, con código de país, ej. `5491122334455`) + un
    **texto** de mensaje pre-cargado (hasta 120). **Va en la tienda (SHOP), no en un producto.**
  - Hasta **8 ítems** en total. Textos **sin `<` ni `>`**.
- **El claim tiene que ser verdad.** "3 cuotas sin interés" o "10% off por transferencia" solo se
  ponen si el comercio realmente lo ofrece: lo confirma el cliente. No se inventan condiciones.
- **Dónde vive cada cosa** (owner):
  - Badges y mensajes → pueden ir **por producto** (owner del producto) o **de toda la tienda**
    (owner del shop). Si el cliente no aclara, preguntá; por defecto, de toda la tienda.
  - WhatsApp → **siempre de toda la tienda** (owner del shop).
- **Sacar = escribir `items: []`** (lista vacía), nunca borrar el metafield (`metafieldDelete` está
  bloqueado). El bloque deja de mostrarse.
- **Sin jerga con el cliente:** todo en lenguaje natural. Nunca nombres de campo, de skill ni comandos.
  Tampoco expliques limitaciones técnicas.
- **Registro:** el que diga `store-standards.md §2` del cliente (blunua: español neutro, SIN voseo).
- **Humanizer obligatorio** antes de todo output cliente: leé `handsOn-Worker/skills/humanizer/SKILL.md`
  y aplicá sus reglas a mano.
- **Nada se escribe sin:** (1) preview mostrado, (2) "sí" explícito, (3) backup guardado.
- **Un asunto por pedido.** El `worker.trust` va solo, nunca mezclado con una oferta, un estilo o una
  FAQ en el mismo `metafieldsSet`.

## Paso 0 — Confirmar cliente y tienda (obligatorio, antes de todo)

1. Confirmá el **cliente activo** y leé `clients/{slug}/CLAUDE.md` + `store-standards.md`.
2. Verificá la tienda conectada con `get-shop-info` contra `clients/{slug}/connection.md`.
3. **Si no coinciden, ABORTÁ.**

## Flujo

1. **Entender qué quiere** (cuotas, transferencia, envío, WhatsApp, un mensaje) y **dónde** (un
   producto puntual o toda la tienda). Si es un badge/mensaje y no aclara, por defecto toda la tienda.
2. **Leer** el `worker.trust` actual (del producto o del shop, según corresponda) para el `previous`
   del backup, y para no pisar ítems que ya estaban (agregás/quitás, no reemplazás a ciegas).
3. **Armar la lista** de ítems, dentro del set cerrado. Confirmá con el cliente los claims (cuántas
   cuotas, qué % por transferencia, qué número de WhatsApp).
4. **Humanizer** sobre todos los textos, con el registro del cliente.
5. **Preview en el chat**, sin jerga: qué va a ver quien entra, y dónde (en el producto / en toda la
   tienda / el botón flotante).
6. **Gate.** Nada sin un "sí" explícito.
7. **Backup** (contrato abajo), ANTES de escribir.
8. **Escribir** el metafield (mutación abajo).
9. **Worklog + confirmar:** "Listo. Para sacarlo: 'sacá el botón de WhatsApp' / 'sacá los sellos'."

## Backup (contrato)

`clients/{slug}/backups/trust/{ownerIdTail}-{YYYYMMDD-HHMMSS}.json`

```json
{ "kind": "trust",
  "productId": "gid://shopify/Product/999",
  "previous": null,
  "ts": "2026-07-22T22:40:00" }
```

- **`kind: "trust"` obligatorio**, carpeta **`backups/trust/`**. Las dos juntas aíslan: un backup de
  confianza no habilita un write de plata ni de otra familia, y viceversa.
- El campo `productId` guarda el **owner** tal cual: el gid del producto **o el del shop**
  (`gid://shopify/Shop/…`) si el ítem es de toda la tienda. El `ownerIdTail` del nombre del archivo es
  la última parte de ese gid.
- `previous` = el `worker.trust` anterior de ese owner, o `null`.
- `ts` en hora local sin zona; vale 15 minutos.

## `escribir` la confianza

```graphql
mutation ($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields { id }
    userErrors { field message }
  }
}
```

```json
{ "metafields": [ {
    "ownerId": "gid://shopify/Shop/1",
    "namespace": "worker",
    "key": "trust",
    "type": "json",
    "value": "{\"version\":1,\"items\":[{\"type\":\"badge\",\"icon\":\"cuotas\",\"text\":\"3 cuotas sin interés\"},{\"type\":\"whatsapp\",\"phone\":\"5491122334455\",\"text\":\"Hola, tengo una consulta\"}]}"
} ] }
```

- **`ownerId` obligatorio**: el gid del producto para badges/mensajes por producto, o el gid del shop
  (`gid://shopify/Shop/…`) para lo de toda la tienda y el WhatsApp.
- `value` es un **string** con el JSON adentro (`type: "json"`).
- El teléfono, **solo dígitos** con código de país. El guard rechaza cualquier otra cosa.

## Sacar

Write como cualquiera (preview → gate → backup → escribir) con `value` = `{"version":1,"items":[]}`
sobre el owner correspondiente. No hay "restore".

## Qué NO hace

- No pone cuotas ni descuentos de verdad: eso es configuración de medios de pago, fuera de alcance.
  Solo muestra el **cartel** de lo que el comercio ya ofrece.
- No captura datos: el WhatsApp abre el chat con un mensaje escrito, nada más.
- No instala los bloques en el tema (eso lo hace el operador una vez; ver el runbook).
