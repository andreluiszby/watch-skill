# /watch — skill de vídeo para o Claude Code

Deixa o Claude "assistir" um vídeo (link ou arquivo local) e responder perguntas sobre ele: o que aparece na tela, o que é dito, em que minuto acontece cada coisa.

```
/watch https://youtu.be/xxxx o que ele fala sobre preço depois dos 10 minutos?
/watch ~/Downloads/reuniao.mp4 resume os pontos de decisão
/watch https://youtu.be/xxxx resume e salva no Obsidian
```

Esta é uma versão própria da skill [`watch`](https://github.com/bradautomates/claude-video) (v0.3.2), com três mudanças nossas listadas [mais abaixo](#o-que-mudou-nesta-versão).

---

## Como funciona

A skill tem dois motores. O setup pergunta qual usar na primeira vez.

| Motor | Como vê o vídeo | Precisa de |
|---|---|---|
| **gemini** (recomendado) | O modelo de vídeo do Google assiste o vídeo inteiro, com áudio, e devolve uma resposta com timestamps. | `GEMINI_API_KEY` grátis em [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| **local** | Baixa o vídeo com `yt-dlp`, extrai frames com `ffmpeg` e pega a transcrição. O Claude olha os frames e lê o texto. | `ffmpeg` e `yt-dlp` |

No motor **local**, a transcrição vem nesta ordem:

1. **Legendas do próprio vídeo** (sempre a primeira opção, e grátis).
2. Se não houver legenda, o fallback escolhido no setup:
   - `whisperx`: roda na sua máquina, sem key, o áudio não sai do computador (~1,5 GB de download na primeira vez)
   - `groq`, `openai` ou **`openrouter`**: transcrição na nuvem, só o áudio é enviado
   - `none`: só legendas

### Nível de detalhe (motor local)

| `--detail` | Frames | Quando usar |
|---|---|---|
| `transcript` | nenhum | Só importa o que é dito |
| `efficient` | até 50, keyframes | Vídeos longos, pergunta geral |
| `balanced` (padrão) | até 100, por mudança de cena | Uso normal |
| `token-burner` | sem limite | Quando cada detalhe visual importa (gasta muito) |

Outras opções úteis: `--start 10:00 --end 15:00` para focar num trecho, `--timestamps 1:23,4:56` para frames em momentos exatos, `--resolution 1024` quando há texto pequeno na tela, `--sub-lang pt` para escolher o idioma da legenda.

---

## O que mudou nesta versão

Em relação ao upstream 0.3.2:

1. **Salvar no Obsidian** (`scripts/obsidian.py`). Só acontece quando você pede ("salva no Obsidian", "salva no vault X"). A nota vai para `<vault>/<canal>/<título>/` com frontmatter (`source`, `channel`, `duration`, `watched`, `tags`), resumo, momentos-chave com timestamps e alguns frames embutidos. Se já existir uma pasta do canal (mesmo com maiúsculas, acentos ou nome mais curto), ela é reaproveitada. Nunca sobrescreve uma nota existente. Em vídeos de terceiros, os momentos-chave viram links para o ponto exato do vídeo em vez de colar a transcrição inteira.
2. **OpenRouter como backend de transcrição** (`openai/whisper-large-v3-turbo`), usando `OPENROUTER_API_KEY`. No modo `auto` a ordem é Groq → OpenAI → OpenRouter.
3. **Correção de legenda em vídeos dublados.** Vídeos com dublagem automática expõem várias faixas `-orig`; agora a skill escolhe a do idioma original em vez da primeira da lista.

---

## Instalação

Requisitos: Python 3.10+. Para o motor local, também `ffmpeg` e `yt-dlp` (no macOS: `brew install ffmpeg yt-dlp`; o setup oferece instalar).

Clone direto na pasta de skills do Claude Code:

```bash
git clone https://github.com/andreluiszby/watch-skill.git ~/.claude/skills/watch
```

Se já existir uma pasta `watch` lá, mova ou apague antes. Depois, abra o Claude Code e rode `/watch` com qualquer vídeo: na primeira vez ele roda o setup e faz as perguntas (motor, nível de detalhe, transcrição).

Para rodar o setup na mão:

```bash
python3 ~/.claude/skills/watch/scripts/setup.py --json
```

Funciona no Claude Code (terminal, VS Code ou aba Code do app desktop). Não funciona no Claude Chat nem no Cowork.

---

## Configuração e keys

**Nenhuma key fica neste repositório.** Tudo fica em `~/.config/watch/.env` (criado pelo setup com permissão `0600`):

```env
# Motor
WATCH_ENGINE=auto            # auto | gemini | local
GEMINI_API_KEY=

# Transcrição (motor local)
WATCH_WHISPER_BACKEND=auto   # auto | groq | openai | openrouter | whisperx | none
GROQ_API_KEY=
OPENAI_API_KEY=
OPENROUTER_API_KEY=

# Padrões
WATCH_DETAIL=balanced        # transcript | efficient | balanced | token-burner
```

Ordem de busca de cada key: variável de ambiente → `~/.config/watch/.env` → `.env` da pasta atual. Um provedor nunca usa a key de outro.

O `.gitignore` bloqueia `.env`, arquivos de cookies e saídas de execução (vídeos, áudios, frames), então um `git add .` acidental não sobe nada disso.

---

## Privacidade

- **gemini**: links do YouTube são enviados ao Google; outros vídeos são enviados para a Files API do Google e apagados depois da resposta (o que não puder ser apagado expira em 48 h).
- **local + whisperx**: nada sai da máquina além do download do vídeo.
- **local + groq/openai/openrouter**: só o áudio extraído vai para o provedor escolhido.
- **Obsidian**: o script só lê o registro de vaults do Obsidian e cria uma pasta de nota no vault escolhido. Não mexe em mais nada.

---

## Estrutura

```
SKILL.md              instruções que o Claude segue
scripts/
  watch.py            ponto de entrada
  setup.py            setup e diagnóstico
  config.py           leitura do ~/.config/watch/.env
  download.py         yt-dlp + escolha de legenda
  frames.py           extração e deduplicação de frames (ffmpeg)
  transcribe.py       parsing de legendas
  whisper.py          transcrição na nuvem (Groq / OpenAI / OpenRouter)
  local_whisperx.py   transcrição local
  gemini.py           motor Gemini
  obsidian.py         salvar nota no Obsidian (adição nossa)
  runtime.py          utilitários de I/O
```

O runtime base usa só a biblioteca padrão do Python. O WhisperX roda num ambiente separado em `~/.cache/watch/whisperx-venv`.

---

## Créditos e licença

Skill original de **Bradley Bonanno** ([bradautomates/claude-video](https://github.com/bradautomates/claude-video)), licença MIT, mantida em [LICENSE](LICENSE). O histórico de versões do upstream está no [CHANGELOG](CHANGELOG.md).
