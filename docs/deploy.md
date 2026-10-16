# Deploy (task 11.1)

Site na **Vercel** (frontend) e API no **Hugging Face Spaces** (backend: api + worker + redis num
contêiner só). Os dois planos gratuitos bastam. Testado localmente: a imagem do Space sobe os três
processos na porta 7860 e converte e exporta documentos.

## 1. Backend no Hugging Face Spaces

1. Crie um Space em https://huggingface.co/new-space — SDK **Docker**, hardware **CPU basic (grátis)**,
   visibilidade **pública** (o navegador precisa alcançar a API sem senha; o código do backend fica
   visível no Space).
2. Envie para o repositório do Space o conteúdo da pasta `backend/` (sem `.venv`, `tests` e caches),
   com `backend/deploy/README.space.md` renomeado para `README.md` na raiz. O `Dockerfile` da raiz
   constrói o estágio `space` (o último).
3. Em *Settings → Variables*, crie `ITT_CORS_ORIGINS` = `["https://SEU-SITE.vercel.app"]`
   (preencha depois do passo 2.3 se ainda não souber o endereço).
4. O primeiro build leva ~15–25 min (baixa os modelos de OCR). Quando terminar, a API responde em
   `https://SEU-USUARIO-NOME-DO-SPACE.hf.space/health`.

## 2. Frontend na Vercel

1. Em https://vercel.com/new, importe o repositório do GitHub.
2. **Root Directory**: `frontend`. Framework: Next.js (detectado).
3. Variável de ambiente `NEXT_PUBLIC_API_URL` = `https://SEU-USUARIO-NOME-DO-SPACE.hf.space`.
4. Deploy. Copie o endereço do site e coloque em `ITT_CORS_ORIGINS` no Space (passo 1.3).

## Limites do plano gratuito

- O Space **dorme após 48 h sem uso**; a primeira visita depois disso espera ~1–2 min para acordar.
- 2 vCPUs: uma conversão por vez (as demais esperam na fila com 0%); ~20–40 s por página.
- Reiniciar o Space apaga tudo (como manda a spec: nada guardado).
