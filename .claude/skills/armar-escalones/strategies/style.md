# Estilo del widget — write de `worker.style`

El look que el cliente elige en el builder (colores + textos). **No mueve plata**, pero es un write
igual, con backup y gate. Es un **asunto separado** de la oferta: va en su propia llamada, nunca
mezclado con los descuentos ni con el metafield `worker.deal`.

## Reglas duras

1. **Solo estas claves**, set cerrado: `ink`, `sage`, `taupe`, `cream` (colores) + `label`, `badge`
   (textos). Cualquier otra clave el guard la rechaza.
2. **Colores en hex** `#RRGGBB` (ej. `#4B4B4B`). Cualquier otra cosa se rechaza (evita inyección de
   CSS por el valor de una var).
3. **Textos** (`label`, `badge`): hasta **40 caracteres**, sin `<` ni `>`.
4. **Backup de estilo ANTES de escribir**, con `kind` y ruta **propios** (ver abajo). El de oferta no
   sirve, y el de estilo no habilita un write de plata (spec §9.1).
5. **Sacar el look = escribir `{}`** (objeto vacío), nunca borrar el metafield: `metafieldDelete`
   está bloqueado. Con `{}`, el widget vuelve a los defaults del `.liquid`.
6. **Un solo estilo por llamada.**

## Backup de estilo (contrato)

Antes de la escritura, guardás:

`clients/{slug}/backups/style/{productIdTail}-{YYYYMMDD-HHMMSS}.json`

```json
{ "kind": "style",
  "productId": "gid://shopify/Product/999",
  "previous": null,
  "ts": "2026-07-22T22:40:00" }
```

- **`kind: "style"` es obligatorio**, y la carpeta **tiene que ser `backups/style/`**. Las dos
  condiciones juntas, igual que el de oferta — es lo que impide que un backup cosmético habilite un
  write de plata.
- `previous` = el `worker.style` anterior tal cual estaba (leelo antes), o `null` si no había.
- Mismo contrato de frescura que los otros: `ts` en hora local sin zona, y vale 15 minutos.

## `escribir` el estilo

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
    "ownerId": "gid://shopify/Product/999",
    "namespace": "worker",
    "key": "style",
    "type": "json",
    "value": "{\"ink\":\"#4B4B4B\",\"sage\":\"#9CB0B1\",\"label\":\"Llevá más y ahorrá\"}"
} ] }
```

- **`ownerId` obligatorio** con el gid del producto (sin él no hay contra qué buscar el backup).
- `value` es un **string** con el JSON adentro (`type: "json"`), no un objeto.
- Solo mandás las claves que el cliente cambió; las que falten, el widget las cae al default
  (fallback por-key). Un `value` `"{}"` resetea todo el look.

## Orden respecto de la oferta

Cuando la config del builder trae oferta **y** look, van en **dos writes separados**, en este orden:
primero la oferta (`automatic.md`: crear descuentos → publicar `worker.deal`), después el estilo.
Cada uno con su propio backup. Nunca los mezcles en un mismo `metafieldsSet`: el guard rechaza el
documento que toca dos asuntos.
