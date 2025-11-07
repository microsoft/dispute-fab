# Scripts Directory

This directory contains utility scripts for managing the SeeHealth Claims Triage application.

## 🪟 Windows Scripts

### `run-services.ps1` (PowerShell)

Main service management script for Windows. Handles starting and stopping both backend and frontend services.

**Features:**
- ✅ Loads environment variables from `.env` file
- ✅ Starts FastAPI backend on port 8000
- ✅ Starts React frontend on port 5173
- ✅ Tracks process IDs for clean shutdown
- ✅ Port conflict detection
- ✅ Graceful service stopping
- ✅ Automatic dependency checking

**Usage from PowerShell:**
```powershell
# Start services
.\scripts\run-services.ps1 start

# Stop services
.\scripts\run-services.ps1 stop
```

**Help:**
```powershell
Get-Help .\scripts\run-services.ps1 -Full
```

### `run-services.bat` (Batch)

Wrapper script for running the PowerShell script from Command Prompt (cmd.exe).

**Usage from Command Prompt:**
```batch
# Start services
scripts\run-services.bat start

# Stop services
scripts\run-services.bat stop
```

## 🍎 macOS/Linux Scripts

### `run-services.sh` (Bash)

Service management script for Unix-like systems (macOS, Linux).

**Features:**
- ✅ Loads environment variables from `.env` file
- ✅ Starts services in background with log files
- ✅ PID tracking for clean shutdown
- ✅ Port conflict detection
- ✅ Color-coded output

**Usage:**
```bash
# Make executable (first time only)
chmod +x scripts/run-services.sh

# Start services
./scripts/run-services.sh start

# Stop services
./scripts/run-services.sh stop

# Check status
./scripts/run-services.sh status
```

## 📋 Prerequisites

### Windows
- **Python 3.11+** with pip
- **Node.js 18+** with npm
- **PowerShell 5.1+** (comes with Windows 10/11)

### macOS/Linux
- **Python 3.11+** with pip
- **Node.js 18+** with npm
- **Bash shell** (standard on macOS/Linux)

## 🔧 Initial Setup

Before running the services for the first time:

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install frontend dependencies:**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

3. **Create `.env` file** (copy from `.env.example`):
   ```bash
   # Windows (PowerShell)
   Copy-Item .env.example .env

   # macOS/Linux
   cp .env.example .env
   ```

4. **Configure Azure OpenAI credentials** in `.env`:
   ```env
   AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
   AZURE_OPENAI_API_KEY=your-api-key-here
   AZURE_OPENAI_DEPLOYMENT_GPT4O=gpt-4o
   ```

## 🚀 Quick Start

### Windows (PowerShell)
```powershell
# From project root
.\scripts\run-services.ps1 start

# Services will be available at:
# - Backend:  http://localhost:8000
# - Frontend: http://localhost:5173
# - API Docs: http://localhost:8000/docs

# When done:
.\scripts\run-services.ps1 stop
```

### Windows (Command Prompt)
```batch
scripts\run-services.bat start
scripts\run-services.bat stop
```

### macOS/Linux
```bash
./scripts/run-services.sh start
./scripts/run-services.sh stop
```

## 📊 Service Endpoints

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:5173 | React dashboard |
| Backend | http://localhost:8000 | FastAPI REST API |
| API Docs | http://localhost:8000/docs | Swagger UI (interactive API docs) |
| ReDoc | http://localhost:8000/redoc | Alternative API documentation |

## 🐛 Troubleshooting

### Port Already in Use

**Windows:**
```powershell
# Find process using port
netstat -ano | findstr :8000

# Kill process by PID
taskkill /PID <pid> /F

# Or use the stop command
.\scripts\run-services.ps1 stop
```

**macOS/Linux:**
```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <pid>

# Or use the stop command
./scripts/run-services.sh stop
```

### Missing Dependencies

**Backend:**
```bash
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

### Environment Variables Not Loading

Ensure `.env` file exists in project root and contains valid Azure OpenAI credentials:
```bash
# Check if file exists
ls -la .env    # macOS/Linux
dir .env       # Windows

# View file (be careful with API keys!)
cat .env       # macOS/Linux
type .env      # Windows
```

### PowerShell Execution Policy Error

If you get "cannot be loaded because running scripts is disabled":

```powershell
# Allow scripts for current user
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Or run with bypass (one-time)
powershell -ExecutionPolicy Bypass -File .\scripts\run-services.ps1 start
```

## 📝 Process Management

### Windows

Process IDs are saved to `.service_pids.json` in the project root. This allows the stop command to gracefully terminate services.

**Manual cleanup:**
```powershell
# Remove PID file
Remove-Item .service_pids.json

# Check running processes
Get-Process | Where-Object {$_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*"}
```

### macOS/Linux

Process IDs are saved to `.backend.pid` and `.frontend.pid`.

**Manual cleanup:**
```bash
# Remove PID files
rm .backend.pid .frontend.pid

# Check running processes
ps aux | grep -E "(uvicorn|vite)"
```

## 🔄 Development Workflow

```bash
# 1. Start services (auto-reload enabled)
./scripts/run-services.ps1 start    # Windows
./scripts/run-services.sh start     # macOS/Linux

# 2. Make code changes (services auto-reload)

# 3. When done for the day
./scripts/run-services.ps1 stop     # Windows
./scripts/run-services.sh stop      # macOS/Linux
```

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React + Vite Documentation](https://vitejs.dev/)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
