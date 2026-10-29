# Setup & Execution Guide — AI Document Understanding Platform

## 1. System Prerequisites

Before running the platform, ensure the following prerequisites are installed:

- **Python**: Version `3.10.x` or higher (tested with Python 3.10.11).
- **Node.js**: Version `18.x` or `20.x` with `npm` (required only if running the React frontend).
- **Git**: For version control.
- **MySQL Database Server (Optional)**: MySQL 8.0+ on `localhost:3306`. If MySQL is not running, the application automatically uses the local SQLite engine (`data/document_platform.db`) with zero configuration needed.

---

## 2. Quick-Start (Automated Setup)

Run the included automated bootstrap script in PowerShell:

```powershell
.\scripts\setup.ps1
```

This script will:
1. Create the Python virtual environment (`venv`).
2. Activate the virtual environment.
3. Upgrade `pip` and install all dependencies from `requirements.txt`.
4. Check and download the spaCy `en_core_web_sm` model.
5. Create `.env` from `.env.example` if not already present.
6. Initialize the database schema.

---

## 3. Manual Installation Step-by-Step

### Step 3.1: Python Virtual Environment Setup

Open PowerShell or Command Prompt in the repository root directory:

```powershell
# Create virtual environment
python -m venv venv

# Activate on Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Activate on Windows (CMD):
.\venv\Scripts\activate.bat

# Activate on Linux/macOS:
source venv/bin/activate
```

### Step 3.2: Install Python Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Step 3.3: Environment Variable Configuration

Copy the template file to `.env`:

```bash
cp .env.example .env
```

Edit `.env` to configure your settings (optional):
```env
SECRET_KEY=your-secure-secret-key
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=intelligent_ocr
DEFAULT_ADMIN_EMAIL=admin@docintel.io
DEFAULT_ADMIN_PASSWORD=Admin@123456
```

---

## 4. Running the Platform

### Option A: Running the Production Flask Platform (Recommended)

To start the complete full-stack web application:

**Using PowerShell:**
```powershell
.\scripts\start_server.ps1
# Or from root:
.\START_SERVER.ps1
```

**Using Windows Batch:**
```bat
scripts\start.bat
# Or from root:
START.bat
```

**Direct Python Command:**
```bash
python app.py
```

The server will initialize on port `5000` and automatically open your default browser.

#### Application URLs:
| Page | URL |
|---|---|
| **Landing & Upload** | [http://127.0.0.1:5000](http://127.0.0.1:5000) |
| **Document Upload** | [http://127.0.0.1:5000/upload](http://127.0.0.1:5000/upload) |
| **Results Viewer** | [http://127.0.0.1:5000/results](http://127.0.0.1:5000/results) |
| **User Dashboard** | [http://127.0.0.1:5000/dashboard](http://127.0.0.1:5000/dashboard) |
| **Admin Portal** | [http://127.0.0.1:5000/auth?portal=admin](http://127.0.0.1:5000/auth?portal=admin) |

---

### Option B: Running the FastAPI Backend & React Frontend

If you wish to run the headless API and React Single-Page Application:

#### 1. Start FastAPI Backend:
```powershell
.\scripts\start_fastapi.ps1
```
*API Swagger Documentation*: [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)

#### 2. Start React Frontend:
In a separate terminal:
```bash
cd frontend
npm install
npm run dev
```
*Frontend URL*: [http://localhost:3000](http://localhost:3000) (Proxies `/api` to port 8000).

---

## 5. Default User Accounts (Development)

| Role | Email | Password | Access Portal |
|---|---|---|---|
| **System Administrator** | `admin@docintel.io` | `Admin@123456` | `/auth?portal=admin` or `/admin/dashboard` |
| **Demo User** | `user@docintel.io` | `User@123456` | `/auth` or `/dashboard` |

> [!WARNING]
> These credentials are seeded for local development and demonstration purposes only. For production deployments, change these passwords immediately or seed customized credentials via `create_admin.py`.

### Creating a New Admin via CLI:
```bash
python create_admin.py --name "Custom Admin" --email "myadmin@example.com" --password "SecurePass2026!"
```

---

## 6. Troubleshooting Common Issues

1. **Port 5000 is already in use:**
   - `scripts/start_server.ps1` automatically detects and clears stale processes holding port 5000.
   - You can also manually kill stale python processes:
     ```powershell
     Get-Process python | Stop-Process -Force
     ```

2. **spaCy model not found (`en_core_web_sm`):**
   - Run: `python -m spacy download en_core_web_sm` within your active virtual environment.

3. **MySQL connection refused:**
   - No action required. The platform automatically detects when MySQL is offline and safely falls back to the embedded SQLite database (`data/document_platform.db`).
