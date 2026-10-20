# Publicação (task 11.1, não executada)

O projeto **não está publicado**. Este documento reúne o que foi preparado e as opções avaliadas em outubro de 2026.

## O que o backend precisa

- **Memória:** cerca de **3 GB**, medidos numa conversão real. Os leitores ocupam quase tudo: docTR ≈ 1,8 GB e PaddleOCR ≈ 1,0 GB. O pico é o mesmo para 1 ou 4 páginas.
- **Processos:** API (FastAPI), fila (Celery) e Redis sempre ligados enquanto há uso, e arquivos guardados por até 1 hora.
- **Processador:** x86, porque o PaddlePaddle não tem versão Linux ARM.
- **Imagem pronta:** o estágio `space` do `backend/Dockerfile` sobe os três processos num contêiner só, na porta 7860 (`backend/deploy/supervisord.conf`). Foi testado localmente.

## Opções avaliadas

| Opção | Custo | Observações |
|---|---|---|
| Hugging Face Spaces (Docker) | ~US$ 9/mês (PRO) | Desde jul/2026, Spaces com Docker exigem o plano PRO. Roda a imagem `space` sem mudanças. |
| Modal | grátis até US$ 30/mês em créditos | Contêiner único que "dorme" após até 20 min sem uso (a 1ª visita espera os modelos carregarem). Estimativa: ~1.900 visitas/mês nos créditos. |
| VPS (Hetzner, Contabo) | ~€ 5–6/mês | Roda o `docker compose` como está. |
| Oracle Cloud Always Free | grátis | Servidor ARM: exigiria ajustes, falta vaga com frequência, e o servidor parado pode ser recolhido. |
| Render / Railway / Vercel | — | O grátis tem 512 MB (Render, Railway), e a Vercel não roda processos contínuos. Os planos que aguentam custam ~US$ 25–85/mês. |

Também foi medida a troca do docTR pelo Tesseract, um leitor mais leve: o pico caiu para ~2,1 GB, mas a precisão piorou sem um ajuste no pareamento das leituras. Não foi adotada.

## Site na Vercel (vale para qualquer opção)

1. Em https://vercel.com/new, importe o repositório.
2. **Root Directory:** `frontend`. Framework: Next.js.
3. Variável `NEXT_PUBLIC_API_URL` com o endereço público do backend.
4. No backend, coloque o endereço do site em `ITT_CORS_ORIGINS` (`["https://SEU-SITE.vercel.app"]`).

## Limites de uso

- 20 páginas e 20 MB por arquivo.
- 3 conversões ativas por endereço.
- Uma conversão por vez no worker, e as outras esperam na fila.
