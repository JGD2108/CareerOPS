# CareerOps Desktop Frontend

React/Vite UI wrapped by Electron.

## Development

From the repo root, prefer:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-desktop.ps1
```

From this folder only:

```powershell
npm install
npm run desktop:dev
```

`desktop:dev` starts Vite and opens the Electron shell.

## Build

```powershell
npm run lint
npm run build
npm run desktop:build
```

The unpacked Electron app is written to `..\dist-desktop\win-unpacked`.

The packaged UI expects the local FastAPI backend at `http://127.0.0.1:8000`.
