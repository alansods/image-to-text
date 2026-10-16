import { describe, expect, it } from "vitest";

import { uploadErrorFor } from "@/lib/api";
import { detectLang, dictionaries } from "@/lib/i18n";

describe("idioma inicial", () => {
  it("inglês quando o navegador prefere inglês, português nos demais casos", () => {
    expect(detectLang(["en-US", "pt-BR"])).toBe("en");
    expect(detectLang(["pt-BR", "en"])).toBe("pt");
    expect(detectLang(["es-ES"])).toBe("pt");
    expect(detectLang([])).toBe("pt");
  });
});

describe("dicionários", () => {
  it("têm as mesmas chaves em PT e EN", () => {
    expect(Object.keys(dictionaries.en).sort()).toEqual(Object.keys(dictionaries.pt).sort());
    expect(Object.keys(dictionaries.en.errors).sort()).toEqual(
      Object.keys(dictionaries.pt.errors).sort(),
    );
  });

  it("contagem de dúvidas no singular e no plural", () => {
    expect(dictionaries.pt.gate(1)).toBe("Confira 1 palavra antes de baixar");
    expect(dictionaries.pt.gate(3)).toBe("Confira 3 palavras antes de baixar");
  });

  it("aviso de qualidade cita as páginas em documentos com várias páginas", () => {
    expect(dictionaries.pt.quality([2], 3)).toContain("A página 2 tem baixa qualidade");
    expect(dictionaries.pt.quality([2, 3], 3)).toContain("As páginas 2 e 3 têm");
    expect(dictionaries.pt.quality([1], 1)).toContain("A imagem tem baixa qualidade");
  });
});

describe("erros de envio", () => {
  it("códigos conhecidos têm mensagem própria; o resto vira falha de envio", () => {
    expect(uploadErrorFor("pdf_password")).toBe("pdf_password");
    expect(uploadErrorFor("algo_estranho")).toBe("network");
  });
});
