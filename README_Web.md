# Capstone Project - Web Security Testing & Management Platform

A comprehensive Docker-based security testing environment featuring DVWA, OWASP Juice Shop, and Nginx WAF (Web Application Firewall) management platform with ModSecurity integration.

## 🎯 Overview

This repository provides a complete security testing and management ecosystem:

- **🛡️ Nginx WAF Management Platform** - Advanced Nginx management with ModSecurity WAF, Domain Management, SSL Certificates, and Real-time Monitoring
- **🔓 DVWA (Damn Vulnerable Web Application)** - Intentionally vulnerable application for security training
- **🧃 OWASP Juice Shop** - Modern vulnerable web application with PostgreSQL backend
- **📊 Comprehensive Logging** - Real-time database and application logging (Vietnam timezone)
- **🔐 ModSecurity WAF** - OWASP Core Rule Set (CRS) protection for all services
- **👥 Multi-user Management** - Role-based access control (Admin/Moderator/Viewer)

## ✨ Key Features

- 🔒 **ModSecurity WAF Protection** - OWASP CRS + Custom Rules for all backend services
- 🌐 **Domain Management** - Load balancing, upstream monitoring, WebSocket support
- 🔐 **SSL Certificate Management** - Auto Let's Encrypt + Manual upload capabilities
- 📊 **Real-time Monitoring** - Performance metrics, alerts, system health dashboards
- 🛡️ **Access Control Lists (ACL)** - IP whitelist/blacklist, GeoIP, User-Agent filtering
- 📋 **Activity Logging** - Comprehensive audit trail and security logs
- 🔔 **Smart Alerts** - Email/Telegram notifications with custom conditions
- 🎨 **Modern Web UI** - React + TypeScript + ShadCN UI + Tailwind CSS

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Git
- PowerShell (Windows) or Bash (Linux/macOS)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/CyberSecN00bers/Capstone_DMZ.git
cd Capstone_Web/web-services
```

2. **Configure environment variables**
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env file with your configurations
# Update the following required variables:
# - JWT_ACCESS_SECRET
# - JWT_REFRESH_SECRET  
# - SESSION_SECRET
# - DB_PASSWORD
# - CORS_ORIGIN (update with your server IP)
# - VITE_API_URL (update with your server IP)
```

3. **Start all services**
```bash
docker compose up -d
```

4. **Access the Nginx WAF Management Portal**
- Open your browser and navigate to: `http://localhost:8080`
- Default login credentials:
  - **Username:** `admin`
  - **Password:** `admin123`

5. **Import the configuration backup**
- After logging in to the portal, go to **Settings** → **Import/Export**
- Click **Import Configuration**
- Select the file: `nginx-love-config-backup.json`
- Click **Import** to restore the pre-configured domains (DVWA and Juice Shop)

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| **Nginx WAF Portal** | `http://localhost:8080` | Main management dashboard |
| **Backend API** | `http://localhost:3001/api` | REST API for management |
| **DVWA** | `http://dvwa.local` | Damn Vulnerable Web Application |
| **Juice Shop** | `http://juiceshop.local` | OWASP Juice Shop |

**Note:** Add these entries to your hosts file:
```
127.0.0.1 dvwa.local
127.0.0.1 juiceshop.local
```

## 📁 Project Structure

```
Capstone_Web/
├── README.md                           # This file
└── web-services/                       # Main application directory
    ├── .env.example                    # Environment variables template
    ├── docker-compose.yml              # Docker Compose configuration
    ├── nginx-love-config-backup.json   # Pre-configured domains backup
    ├── config/                         # Configuration files
    │   ├── mysql-logging.cnf          # MySQL logging configuration
    │   └── postgres-logging.conf      # PostgreSQL logging configuration
    ├── logs/                          # Runtime logs (bind-mounts)
    │   ├── apache/                    # DVWA Apache logs
    │   ├── juiceshop/                 # Juice Shop application logs
    │   ├── mysql/                     # MariaDB logs
    │   └── postgres/                  # PostgreSQL logs
    └── nginx-love/                    # Nginx WAF Management Platform
        ├── apps/
        │   ├── api/                   # Backend API (Node.js + Prisma)
        │   ├── web/                   # Frontend (React + TypeScript)
        │   └── docs/                  # Documentation
        ├── config/
        │   └── nginx.conf             # Nginx configuration
        └── docker/                    # Docker build files
```

## 🔧 Configuration

### Environment Variables

Key environment variables in `.env`:

```bash
# Database Configuration
DB_NAME=nginx_waf
DB_USER=postgres
DB_PASSWORD=postgres

# API Configuration
API_PORT=3001
NODE_ENV=production

# Frontend Configuration
WEB_PORT=8080
VITE_API_URL=http://YOUR_SERVER_IP:3001/api

# JWT Secrets (generate with: openssl rand -base64 32)
JWT_ACCESS_SECRET=your-random-secret-key-32-chars
JWT_REFRESH_SECRET=your-random-secret-key-32-chars
SESSION_SECRET=your-random-secret-key-32-chars

# CORS Configuration
CORS_ORIGIN=http://YOUR_SERVER_IP:8080,http://localhost:8080

# Timezone
TZ=Asia/Ho_Chi_Minh
```

### Default Users

After importing the configuration backup, these users are available:

| Username | Password | Role | Description |
|----------|----------|------|-------------|
| `admin` | `admin123` | Admin | Full system access |
| `operator` | `operator123` | Moderator | Limited management access |
| `viewer` | `viewer123` | Viewer | Read-only access |

**⚠️ Security Warning:** Change all default passwords immediately after first login!

## 🛠️ Management Operations

### Starting Services
```bash
cd web-services
docker compose up -d
```

### Stopping Services
```bash
cd web-services
docker compose down
```

### Viewing Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f dvwa
docker compose logs -f juiceshop
```

### Restarting Services
```bash
docker compose restart
```

### Updating Services
```bash
cd web-services
docker compose pull
docker compose up -d
```

## 📊 Monitoring & Logs

### Application Logs
- **Nginx WAF Logs:** Accessible via the web portal under **Logs** section
- **Apache Logs (DVWA):** `web-services/logs/apache/`
- **PostgreSQL Logs:** `web-services/logs/postgres/`
- **MySQL Logs:** `web-services/logs/mysql/`
- **Juice Shop Logs:** `web-services/logs/juiceshop/`

### Health Checks
All services include health checks that can be monitored via:
```bash
docker compose ps
```

### Container Status
```bash
docker ps -a
```

## 🔐 Security Features

### ModSecurity WAF Rules (Pre-configured)

The imported configuration includes these OWASP CRS rules:

- ✅ **SQL Injection Protection** - REQUEST-942-APPLICATION-ATTACK-SQLI.conf
- ✅ **XSS Attack Prevention** - REQUEST-941-APPLICATION-ATTACK-XSS.conf
- ✅ **RCE Detection** - REQUEST-932-APPLICATION-ATTACK-RCE.conf
- ✅ **Session Fixation** - REQUEST-943-APPLICATION-ATTACK-SESSION-FIXATION.conf
- ✅ **PHP Attacks** - REQUEST-933-APPLICATION-ATTACK-PHP.conf
- ✅ **Protocol Attacks** - REQUEST-920-PROTOCOL-ENFORCEMENT.conf
- ✅ **SSRF Protection** - REQUEST-934-APPLICATION-ATTACK-GENERIC.conf
- ✅ **Web Shell Detection** - RESPONSE-955-WEB-SHELLS.conf
- ❌ **LFI Protection** - REQUEST-930-APPLICATION-ATTACK-LFI.conf (disabled)
- ❌ **Data Leakage** - RESPONSE-950-DATA-LEAKAGES.conf (disabled)

### Access Control
- IP-based whitelist/blacklist
- GeoIP filtering
- User-Agent filtering
- Rate limiting

## 🐛 Troubleshooting

### Common Issues

**1. Containers fail to start**
```bash
# Check container logs
docker compose logs

# Verify network exists
docker network ls | grep capstone-network

# Recreate network if needed
docker network create capstone-network
```

**2. Cannot access web portal**
- Verify port 8080 is not in use: `netstat -ano | findstr :8080`
- Check CORS_ORIGIN in `.env` includes your access URL
- Verify frontend container is running: `docker ps | grep frontend`

**3. Database connection errors**
- Wait for database initialization (30-40 seconds on first start)
- Check database health: `docker compose ps postgres-nginx-love`
- View database logs: `docker compose logs postgres-nginx-love`

**4. Configuration import fails**
- Ensure you're logged in as admin
- Verify the backup file is valid JSON
- Check backend logs: `docker compose logs backend`

**5. DVWA or Juice Shop not accessible**
- Add hosts entries (see Access Points section)
- Verify containers are running: `docker ps`
- Check backend nginx configuration was applied
- Restart backend: `docker compose restart backend`

### Log Collection
```bash
# Collect all logs for debugging
docker compose logs > debug-logs.txt

# Or specific service
docker compose logs backend > backend-logs.txt
```

### Reset Everything
```bash
# Stop and remove all containers, volumes
docker compose down -v

# Remove network
docker network rm capstone-network

# Start fresh
docker network create capstone-network
docker compose up -d
```

## 📚 Documentation

For detailed documentation about the Nginx WAF Management Platform, see:
- `web-services/nginx-love/README.md` - Platform overview and features
- `web-services/nginx-love/apps/docs/` - Complete documentation

## 🤝 Contributing

This is a Capstone project. For questions or issues, contact the project team.

## 📝 License

This project integrates multiple components with their respective licenses:
- Nginx WAF Management Platform: See `web-services/nginx-love/LICENSE`
- DVWA: GPL License
- OWASP Juice Shop: MIT License

## ⚠️ Disclaimer

This environment contains intentionally vulnerable applications for educational and testing purposes. **Do NOT expose these services to the public internet.** Use only in isolated, controlled environments.

## 🙏 Acknowledgments

- [Nginx WAF Management Platform](https://github.com/TinyActive/nginx-love) by TinyActive
- [DVWA](https://github.com/digininja/DVWA) by digininja
- [OWASP Juice Shop](https://github.com/juice-shop/juice-shop)
- [ModSecurity](https://github.com/SpiderLabs/ModSecurity)
- [OWASP Core Rule Set](https://github.com/coreruleset/coreruleset)

---

**Project Team:** CyberSecN00bers  
**Repository:** https://github.com/CyberSecN00bers/Capstone_DMZ
