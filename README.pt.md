# Cadence

[English](README.md) · [Português](README.pt.md)

Uma aplicação de música autoalojada para ensinar o teu gosto, avaliar propostas diárias, gerir playlists e acompanhar downloads aprovados até ao Emby e ao Symfonium.

**Alpha inicial.** Esta é a primeira distribuição independente, extraída de uma instalação pessoal. A interface tem catálogos em inglês e português; algumas mensagens dos fornecedores e registos do backend ainda aparecem em português.

## O que inclui

Cadence, os seus workers, Emby e slskd. **Não inclui Immich, fotografias, Proxmox, criação de CTs, instalação do sistema operativo nem configuração da Cloudflare.** Cada pessoa escolhe o servidor, armazenamento e acesso remoto. Emby, Soulseek e Symfonium são produtos separados, com os seus próprios termos e licenças.

## Instalação

Requer Docker Engine, Docker Compose v2, Git e uma shell POSIX. São necessários containers Linux. O instalador não instala Docker nem altera a firewall.

```sh
git clone https://github.com/stevengdc/cadence.git && cd cadence && sh install.sh
```

A primeira execução compila a aplicação. Abre `http://localhost:8787`. O utilizador inicial é `admin`; a password é gerada localmente e fica em `.secrets/admin-password`. Não existe uma password partilhada de fábrica. Edita `.env` antes de iniciar para mudar portas, endereço da rede, fuso horário ou ligações públicas. A interface começa em inglês; podes escolher Português no login ou na barra superior.

### Ligar os serviços

1. Abre o Emby em `http://localhost:8096`, conclui a configuração e adiciona uma biblioteca de **Música** em `/media/music`. Ativa os fornecedores de metadados e imagens que pretendes.
2. Cria uma chave API no Emby e executa:

   ```sh
   docker compose run --rm cadence python configure.py
   ```

3. Introduz o endereço interno do Emby, a chave e a conta a associar. Opcionalmente, configura o Soulseek; depois reinicia o serviço:

   ```sh
   docker compose restart slskd
   ```

4. Classifica músicas e cria playlists. Os downloads começam **pausados** e só são retomados explicitamente no Cadence. Antes de converter uma biblioteca existente, garante uma cópia recuperável.

No Symfonium, adiciona o endereço e a conta Emby. Usa um endereço acessível pelo telemóvel. TLS, VPN, encaminhamento de portas e acesso remoto são decisões do teu ambiente. As portas web ficam limitadas a localhost por defeito; a porta de peers do Soulseek é publicada separadamente e deve ser revista para a tua rede.

## Dados e backups

`data/` contém o estado, música, downloads, configurações e backups locais. `.secrets/` guarda a password inicial. Nenhuma destas pastas entra no Git. O Emby recebe a música apenas para leitura; o slskd recebe a pasta de redistribuição apenas para leitura. A partilha exige autorização explícita de cada ficheiro elegível. Partilha apenas material cuja redistribuição podes autorizar.

O backup SQLite local **não** inclui a música nem substitui um backup externo. Faz cópias de `data/` e `.secrets/` para um destino separado.

## Gestão

```sh
docker compose ps
docker compose logs --tail=100 cadence worker
docker compose stop
docker compose up -d
```

Antes de atualizar, lê as notas da versão e faz backup. A atualização e recuperação de bases de dados precisam de validação antes de uma versão estável.

O código está em `backend/` e `ui/`. Os idiomas ficam em `ui/src/locales/`. Consulta [README.md](README.md) para desenvolvimento e o roteiro. Próximas etapas: tradução completa do backend, assistente web de configuração, fornecedores de tops configuráveis e imagens de release versionadas. Esta versão não exige uma API de IA.

Consulta [SECURITY.md](SECURITY.md) antes de reportar problemas. Não publiques bases de dados, música, passwords, tokens ou imagens com informação pessoal. A escolha de licença aguarda confirmação antes da primeira release pública.

Validação inicial: 99 testes passaram dentro do container; uma instalação Compose vazia arrancou e o login do administrador devolveu HTTP 200. A configuração das contas dos fornecedores continua manual.
