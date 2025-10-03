# Aukpad

Simple **live collaboration notepad** with websockets and FastAPI.

[Issue tracker](https://git.uphillsecurity.com/cf7/aukpad/issues) | `Libera Chat #aukpad` 

- Status: Beta - expect minor changes.
- Instance/Demo: [aukpad.com](https://aufkpad.com/)
- Inspired by:
    - [Rustpad](https://github.com/ekzhang/rustpad)

The goal is to keep it simple! For feature-rich solutions are [hedgedoc](https://github.com/hedgedoc/hedgedoc) or [codeMD](https://github.com/hackmdio/codimd).

---

## Features

**Use cases:**
- shared notepad on multiple machines
- collaboration on the same notepage with multiple people (notes, config, etc)
- config changes in aukpad > `curl -o app.conf https://aukpad.com/{pad_id}/raw` > change config in aukpad > repeat `curl` command

**Available**:
- live collab notepad
- line numbers
- custom path `{pad_id}` for more privacy
- optional caching with valkey/redis
- pad creation with HTTP post requests with curl (see *Usage*)
- `{pad_id}/raw` HTTP endpoint 

**Ideas**:
[Check out the open feature requests](https://git.uphillsecurity.com/cf7/aukpad/issues?q=&type=all&sort=&state=open&labels=12&milestone=0&project=0&assignee=0&poster=0&archived=false)

**Not planned**:
- accounts / RBAC

---

## Usage

**Creating pad with curl**

```bash
curl -X POST -d "Cheers" https://aukpad.com/                  # string
curl -X POST https://aukpad.com --data-binary @- < file.txt   # file
ip -br a | curl -X POST https://aukpad.com --data-binary @-   # command output
```

---

## Installation

**Please use a reverse proxy and TLS in production!**

### Docker

**Simple / Testing**

`docker run -p 127.0.0.1:8000:8000 git.uphillsecurity.com/cf7/aukpad:latest`

Open `127.0.0.1:8000`

**Adv. example with Podman**

```bash
# Create Pod
podman pod create --name aukpad-pod -p 127.0.0.1:8000:8000

# Start Valkey Container (or replace with redis)
podman run -d --name aukpad-cache \
    --replace \
    --pod aukpad-pod \
    --restart=unless-stopped \
    docker.io/valkey/valkey:7 \
    --requirepass xeZNopyIeMMncqDFPHtJQwMwIathgMWo \
    --maxmemory 2gb \
    --maxmemory-policy allkeys-lru \
    --save "" \
    --appendonly no \
    --bind 0.0.0.0 \
    --protected-mode yes

# Start aukpad Container
podman run -d --name aukpad-app \
    --replace \
    --pod aukpad-pod \
    --read-only \
    --tmpfs /tmp \
    --security-opt no-new-privileges:true \
    --cap-drop ALL \
    --user 1000:1000 \
    -e USE_VALKEY=true \
    -e VALKEY_URL=redis://:xeZNopyIeMMncqDFPHtJQwMwIathgMWo@localhost:6379 \
    -e MAX_TEXT_SIZE=5 \
    -e MAX_CONNECTIONS_PER_IP=20 \
    -e RETENTION_HOURS=72 \
    git.uphillsecurity.com/cf7/aukpad:latest
```

*Tested only with Podman - Docker-Compose file might follows.*

Enable support for web sockets in your reverse proxy of choice! - Nginx config example will be added at some point.

### Environment Variables

The following environment variables can be configured:

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_VALKEY` | `false` | Enable Valkey/Redis caching. Set to `true` to enable |
| `VALKEY_URL` | `redis://localhost:6379/0` | Redis/Valkey connection URL |
| `MAX_TEXT_SIZE` | `5` | Maximum text size in MB (5MB default) |
| `MAX_CONNECTIONS_PER_IP` | `10` | Maximum concurrent connections per IP address |
| `RETENTION_HOURS` | `48` | How long to retain pads in hours after last access |
| `DESCRIPTION` | `powered by aukpad.com` | Instance description shown on info page |

---

## Security

For security concerns or reports, please contact via `hello a t uphillsecurity d o t com` [gpg](https://uphillsecurity.com/gpg).

---

## Notes

- [Github Mirror available](https://github.com/CaffeineFueled1/aukpad)

---

## License

**Apache License**

Version 2.0, January 2004

http://www.apache.org/licenses/

- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- ✅ Patent use
- ✅ Private use
- ✅ Limitations
- ❌Trademark use
- ❌Liability
- ❌Warranty
