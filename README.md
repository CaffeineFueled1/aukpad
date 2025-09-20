# Aukpad

Simple **live collaboration notepad** with websockets and FastAPI.

- Status: Beta - expect minor changes.
- Instance/Demo: [aukpad.com](https://aufkpad.com/)
- Inspired by:
    - [Rustpad](https://github.com/ekzhang/rustpad)

The goal is to keep it simple! For feature-rich solutions are [hedgedoc](https://github.com/hedgedoc/hedgedoc) or [codeMD](https://github.com/hackmdio/codimd).

---

## Features

**Available**:
- live collab notepad
- line numbers
- custom path for more privacy
- optional caching with valkey/redis
- pad creation with HTTP post requests with curl (see *Usage*)
- `[pad_id]/raw` HTTP endpoint 

**Ideas**:
- read-only views
- password protection
- E2EE
- caching/ auto-save to localstorage in browser / offline use

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

WORK IN PROGRESS

---

## Security

For security concerns or reports, please contact via `hello a t uphillsecurity d o t com` [gpg](https://uphillsecurity.com/gpg).

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
