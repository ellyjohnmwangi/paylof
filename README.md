# PAYLOFT - Transaction-Based POS System

A pay-per-use Point of Sale system designed for Kenya's informal retail sector.

## Quick Start

### Backend
```bash
cd PAYLOFT
source venv/bin/activate
python manage.py runserver
```
Server runs on http://127.0.0.1:8000

### Frontend
```bash
cd frontend
npm start
```
App runs on http://localhost:3000

### Admin Access
- URL: http://127.0.0.1:8000/admin
- Username: admin
- Password: admin123

## Features
- SME business workspaces with token authentication
- Role-based access control for owners, managers, and cashiers
- Product management with inventory tracking
- Transaction processing with automatic stock updates and oversell protection
- Pay-per-transaction fee calculation (KES 2-5)
- Cash checkout and Safaricom Daraja M-Pesa STK Push payments
- Paid reports paywall with daily, weekly, and monthly report subscriptions
- Offline sale queue with later sync from the frontend
- Sales history, low-stock alerts, and reporting
- User and distributor management
- English/Swahili frontend language toggle
- Mobile-responsive PWA interface
- RESTful API for integrations

## API Endpoints
- POST /api/auth/login/ - Authenticate and receive an API token
- POST /api/auth/register/ - Create a new SME owner workspace
- GET /api/auth/me/ - View current authenticated user and role
- GET /api/products/ - List products
- GET /api/products/low_stock/ - List products at or below their alert threshold
- GET/POST /api/distributors/ - Manage distributors
- GET/POST /api/users/ - Manage business users
- POST /api/sales/create_sale/ - Create new sale
- GET /api/sales/ - View sales history
- GET /api/sales/analytics/ - View sales totals, fees, low-stock count, and top products
- POST /api/mpesa/stk-push/ - Send STK Push for an existing pending M-Pesa sale
- POST /api/mpesa/callback/ - Safaricom Daraja callback endpoint
- GET /api/mpesa/payment-status/<payment_id>/ - Check M-Pesa payment status
- GET/POST /api/reports/subscription/ - View report access or start STK payment for a daily, weekly, or monthly reports plan
- GET /api/reports/subscription/payment-status/<payment_id>/ - Check report-plan M-Pesa payment status

## Daraja Setup

Copy `.env.example` to `.env`, fill in your Daraja app credentials, and set `MPESA_CALLBACK_URL` to a public URL that points to `/api/mpesa/callback/`. For local testing, expose Django with a tunnel such as `ngrok http 8000` and use that HTTPS URL.

M-Pesa sales are created as `pending`, then marked `paid` only after Safaricom sends a successful callback. Failed, cancelled, or timed-out STK requests mark the sale failed and restore the reserved stock.

## Report Paywall

All reports require an active report subscription. The frontend blurs locked report content and displays purple pricing options. A user selects a plan, enters their M-Pesa phone number, and receives an STK Push. Reports unlock only after the Daraja callback confirms payment.
- Daily: KES 30
- Weekly: KES 180
- Monthly: KES 700

## Demo
See DEMO_SCRIPT.md for detailed demonstration steps.

## Tech Stack
- Backend: Django 6.0.4 + DRF
- Frontend: React 18 PWA
- Database: SQLite
- Authentication: Django Auth
