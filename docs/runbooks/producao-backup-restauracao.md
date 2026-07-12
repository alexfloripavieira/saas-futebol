# Produção, backup e restauração

## Runtime

O deploy usa `docker-compose.prod.yml`, Gunicorn e o módulo
`config.settings_production`. O PostgreSQL não publica porta no host; somente a
aplicação o acessa pela rede interna do Compose. A porta HTTP da aplicação fica
restrita a `127.0.0.1` para ser publicada por um proxy TLS.

Antes do primeiro deploy:

1. copie `.env.example` para `.env.production` e substitua todos os segredos;
2. configure `DJANGO_ALLOWED_HOSTS` e `DJANGO_CSRF_TRUSTED_ORIGINS` com os domínios HTTPS;
3. mantenha `DJANGO_SECURE_SSL_REDIRECT`, cookies seguros e HSTS habilitados;
4. configure o proxy para enviar `X-Forwarded-Proto: https`;
5. nunca exponha `/midia-privada/` como diretório estático.

Subida e validação:

```sh
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml exec web python src/manage.py check --deploy
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

O health check usa `GET /health/`, envia o cabeçalho do proxy HTTPS e só aceita
o corpo `{"status": "ok"}` depois de uma consulta real ao banco. A rota não
exige login nem retorna dados internos.

## Evidências privadas

Os arquivos ficam no volume `media_data`, segregados por ID de tenant e com nome
aleatório. O acesso deve ocorrer por uma view autenticada, nunca pelo servidor
de arquivos. Essa view deve buscar `Evidence` no tenant ativo, aplicar
`user_can_download_evidence` de `futebol.services.evidence_files` e entregar o
arquivo com `FileResponse` e `Content-Disposition: attachment`.

O volume de mídia possui backup próprio; o dump do banco, sozinho, não contém
os arquivos de evidência.

## Backup do PostgreSQL

Crie um dump manual com checksum:

```sh
docker compose --env-file .env.production -f docker-compose.prod.yml --profile ops run --rm backup
docker compose --env-file .env.production -f docker-compose.prod.yml --profile ops run --rm media-backup
```

Copie os dumps e snapshots do volume de mídia para armazenamento externo,
criptografado e com política de retenção. Recomendação inicial para o piloto:
backup diário, retenção de 30 dias e uma cópia fora do host.

## Ensaio de restauração

Faça o ensaio em banco descartável e isolado. Nunca use primeiro o banco ativo.

```sh
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm \
  --entrypoint /bin/sh backup \
  /scripts/restore_postgres.sh /backups/saas_futebol_AAAAMMDDTHHMMSSZ.dump
```

Depois da restauração, execute migrações, `manage.py check`, conte registros
críticos por tenant e valide uma jornada de login e aprovação. Registre data,
responsável, duração e resultado do ensaio. Repita ao menos mensalmente.

Para restaurar a mídia no ambiente isolado:

```sh
docker compose --env-file .env.production -f docker-compose.prod.yml --profile restore run --rm \
  media-restore /backups/media_AAAAMMDDTHHMMSSZ.tar.gz
```

## Logs e alertas

Gunicorn escreve access/error logs em stdout. O formatter Django inclui o
`request_id`, que também é devolvido no header `X-Request-ID`. O coletor de logs
deve preservar esse campo e alertar para taxa de respostas 5xx, health check
indisponível e falhas repetidas de autorização. Configure uma ferramenta de
monitoramento de erros no ambiente antes do go-live e evite enviar conteúdo de
evidências ou segredos como contexto do erro.
