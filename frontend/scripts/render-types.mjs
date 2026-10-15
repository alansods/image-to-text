// Converte um JSON Schema (exportado do backend) no código TypeScript de lib/types/*.ts.
import { compile } from "json-schema-to-typescript";

export const TYPE_NAMES = ["document", "job"];

const BANNER =
  "/* Gerado por `npm run gen:types` a partir de backend/app/models. Não edite à mão. */";

export function renderTypes(schema) {
  return compile(schema, schema.title, {
    bannerComment: BANNER,
    additionalProperties: false,
    style: { semi: true, singleQuote: false, printWidth: 100 },
  });
}
