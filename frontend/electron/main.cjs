const { app, BrowserWindow, shell } = require('electron')
const path = require('node:path')

const DEV_SERVER_URL = process.env.CAREEROPS_DESKTOP_URL || 'http://localhost:5173'
let mainWindow = null

function parseUrl(value) {
  try {
    return new URL(value)
  } catch {
    return null
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1180,
    minHeight: 760,
    title: 'CareerOps Agent',
    backgroundColor: '#f5f7fb',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    const targetUrl = parseUrl(url)
    const currentUrl = parseUrl(mainWindow?.webContents.getURL() || DEV_SERVER_URL)

    // Ignore popup attempts that resolve to blank pages instead of opening empty windows.
    if (!targetUrl || targetUrl.protocol === 'about:') {
      return { action: 'deny' }
    }

    // Keep same-origin navigations inside the existing app shell.
    if (currentUrl && targetUrl.origin === currentUrl.origin) {
      return { action: 'deny' }
    }

    if (targetUrl.protocol === 'http:' || targetUrl.protocol === 'https:') {
      shell.openExternal(targetUrl.toString())
    }
    return { action: 'deny' }
  })

  mainWindow.webContents.on('will-navigate', (event, url) => {
    const currentUrl = parseUrl(mainWindow.webContents.getURL())
    const nextUrl = parseUrl(url)
    const isSameAppNavigation =
      url.startsWith('file://') ||
      (currentUrl && nextUrl && currentUrl.origin === nextUrl.origin)

    if (!isSameAppNavigation && nextUrl && (nextUrl.protocol === 'http:' || nextUrl.protocol === 'https:')) {
      event.preventDefault()
      shell.openExternal(nextUrl.toString())
    }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  if (app.isPackaged) {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  } else {
    mainWindow.loadURL(DEV_SERVER_URL)
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  }
}

app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
