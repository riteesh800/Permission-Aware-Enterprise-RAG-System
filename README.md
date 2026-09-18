# Permission-Aware RAG System

A sophisticated Retrieval-Augmented Generation (RAG) system with built-in Role-Based Access Control (RBAC). It provides separate portals for Administrators and Employees, enforcing strict access controls on both document management and query retrieval.

## Overview

This project implements a full-stack, secure RAG platform where organizational documents are ingested, vectorized, and securely queried. The system is designed to ensure that users can only retrieve information from documents they are authorized to access.

## Key Features

*   **Role-Based Access Control (RBAC):** Distinct `ADMIN` and `EMPLOYEE` roles with specific permission scopes.
*   **Vector Search Engine:** Leverages PostgreSQL with the `pgvector` extension for efficient semantic similarity search.
*   **Comprehensive Document Support:** Parses and ingests a variety of formats including PDF, DOCX, XLSX, and CSV (powered by PyMuPDF, python-docx, and pandas).
*   **Admin Dashboard:** Interfaces for managing users, handling document uploads/ingestion, and viewing system-wide audit logs.
*   **Employee Chat Interface:** A conversational interface for employees to query the RAG system, complete with session history.
*   **Audit Logging:** Tracks all critical user actions and system events for security and compliance.
*   **Secure Authentication:** JWT-based authentication with secure Argon2 password hashing.

## Tech Stack

### Frontend
*   **Framework:** React 18 with TypeScript
*   **Build Tool:** Vite
*   **Routing:** React Router DOM

### Backend
*   **Framework:** FastAPI
*   **Database ORM:** SQLAlchemy 2.0
*   **Database Migration:** Alembic
*   **Core Database:** PostgreSQL
*   **Vector Storage:** pgvector
*   **Authentication:** python-jose (JWT), argon2-cffi

## Getting Started

### Prerequisites
*   Node.js (v18+)
*   Python 3.9+
*   PostgreSQL (with the `pgvector` extension installed)

### Backend Setup

1.  Navigate to the backend directory:
    ```bash
    cd backend
    ```
2.  Create and activate a virtual environment:
    ```bash
    python -m venv .venv
    # On Windows: .venv\Scripts\activate
    # On macOS/Linux: source .venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Configure Environment Variables:
    *   Copy `.env.example` to `.env` (if provided) or create a `.env` file based on your database configuration.
    *   Ensure the database URL correctly points to your PostgreSQL instance with `pgvector` enabled.
5.  Run Database Migrations:
    ```bash
    alembic upgrade head
    ```

### Frontend Setup

1.  Navigate to the frontend directory:
    ```bash
    cd frontend
    ```
2.  Install dependencies:
    ```bash
    npm install
    ```

## Running the Application

Once you have completed the setup steps above, you can run the application by starting both the backend and frontend servers in separate terminal windows.

### 1. Run the Backend Server
Open a terminal, navigate to the `backend` directory, activate your virtual environment, and run:
```bash
uvicorn app.main:app --reload
```
*The backend API will be available at `http://localhost:8000`.*

### 2. Run the Frontend Server
Open a new terminal, navigate to the `frontend` directory, and run:
```bash
npm run dev
```
*The frontend application will be available at `http://localhost:5173`.*

## Project Structure

```text
├── backend/
│   ├── alembic/       # Database migration scripts
│   ├── app/           # Core FastAPI application
│   │   ├── api/       # API endpoints (auth, chat, admin)
│   │   ├── models/    # SQLAlchemy database models
│   │   ├── ...
│   ├── requirements.txt
│   └── ...
├── frontend/
│   ├── src/           # React frontend source code
│   │   ├── components/# Reusable UI components
│   │   ├── pages/     # Page layouts (Admin, Employee, Auth)
│   │   ├── ...
│   ├── package.json
│   └── ...
```

## Security

For detailed information on the security architecture, authentication flow, and data protection measures, please review the security guidelines or the architecture documentation within the repository.
