// Gera os tipos TypeScript do formato interno a partir dos modelos Pydantic do backend.
// Fonte da verdade: backend/app/models. Nunca edite lib/types/*.ts à mão.
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { renderTypes, TYPE_NAMES } from "./render-types.mjs";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const backend = join(root, "..", "backend");
const schemaDir = join(root, "lib", "types", "schema");

execFileSync("uv", ["run", "python", "-m", "scripts.export_schema", schemaDir], {
  cwd: backend,
  stdio: "inherit",
});

for (const name of TYPE_NAMES) {
  const schema = JSON.parse(readFileSync(join(schemaDir, `${name}.schema.json`), "utf8"));
  writeFileSync(join(root, "lib", "types", `${name}.ts`), await renderTypes(schema));
  console.log(`lib/types/${name}.ts gerado`);
}
