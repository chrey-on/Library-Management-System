# 📚 Library Management System (Web Case Study)

**Course:** Database 2 (IT31A)  
**Architecture:** Python (Flask) + MySQL / MariaDB (XAMPP) + Bootstrap 5 + Vanilla JS  
**Repository:** [github.com/chrey-on/Library-Management-System](https://github.com/chrey-on/Library-Management-System.git)

---

## 🌟 Project Overview

A full-stack, production-grade **Library Management System** engineered to demonstrate database normalization (**3NF**), relational integrity constraints, automated business logic via **Database Triggers**, multi-statement **Stored Procedures**, analytical **Views**, and Role-Based Access Control (**RBAC**).

### ✨ Key Features

1. **Role-Based Authentication & Security:**
   - Dual-role system (**Librarians / Administrators** vs. **Student Members**).
   - Password hashing with PBKDF2 (`werkzeug.security`).
   - Session management with active-account checking and CSRF/SQL Injection protection using parameterized queries.
2. **Book & Physical Copy Inventory (`vw_book_catalog`):**
   - Book cataloging with ISBN, title, publisher, year, and category.
   - Multi-author support via the `book_authors` junction table (many-to-many relationship).
   - Physical copy management with auto-generated accession numbers (`ACC-XXXX`) and copy lifecycle statuses (`available`, `borrowed`, `lost`, `damaged`).
   - Non-destructive soft delete (archiving/restoring titles).
3. **Student Member Management:**
   - Atomic student registration creating `users` and `members` records within a database transaction.
   - Course and year-level classification (`courses` lookup table in 3NF).
   - Account deactivation safety checks (blocks deactivating students with unreturned books).
   - Student self-service portal: personal borrowing history, return due date countdowns, and outstanding fine statements.
4. **Automated Circulation Engine (Stored Procedures & Triggers):**
   - **Check Out (`sp_borrow_book`):** Validates copy availability, student loan limit (max 3), overdue books, and fine balances at the database engine level via `trg_loans_before_insert`. Automatically updates physical copy status to `'borrowed'` via `trg_loans_after_insert`.
   - **Check In / Return (`sp_return_book`):** Transaction-safe return handler. Automatically calculates late days and assesses ₱5.00/day fines into the ledger while restoring copy status to `'available'` via `trg_loans_after_update`.
   - **Fine Settlement (`sp_pay_fine`):** Settle overdue penalties and record transaction timestamps and librarian audits.
5. **Analytics & Printable Reports with Chart.js:**
   - **Interactive Dashboards:** Live circulation metrics and Chart.js monthly trend visualizations.
   - **Most Borrowed Titles Report (`vw_most_borrowed_books`)**: Ranked book popularity leaderboard.
   - **Overdue Books & Delinquency Audit**: Detailed overdue loans with student contact info.
   - **Unpaid Fines Ledger (`vw_member_unpaid_fines`)**: Real-time listing of delinquent accounts.
   - **Monthly Circulation Summary (`sp_monthly_borrow_summary`)**: Annual circulation breakdown with print-friendly CSS.

---

## 🗄️ Database Design & Schema Highlights

### Database Architecture Diagram (ERD)

```text
  [USERS] (user_id PK)
     │ 1:1
     ├───► [MEMBERS] (member_id PK, user_id FK, course_id FK) ◄─── [COURSES]
     │        │ 1:N
     │        └───► [LOANS] (loan_id PK, copy_id FK, member_id FK, issued_by FK)
     │                 │ 1:1                                           │
     │                 ├───► [FINES] (fine_id PK, loan_id FK)          │ N:1
     │                 │                                               ▼
     │                 └─────────────────────────────────────► [BOOK_COPIES] (copy_id PK)
     │                                                                 │ N:1
     └────────────────────────────────────────────────────────► [BOOKS] (book_id PK)
                                                                 ├── [CATEGORIES] (category_id FK)
                                                                 └── [BOOK_AUTHORS] ◄── [AUTHORS]
```

### Stored Procedures
- **`sp_borrow_book(p_member_id, p_copy_id, p_librarian_id)`**: Issues book copy and computes 7-day due date from `library_settings`.
- **`sp_return_book(p_loan_id, p_librarian_id)`**: Processes return in transaction, assesses overdue fines if returned late, and updates copy availability.
- **`sp_pay_fine(p_fine_id, p_librarian_id)`**: Settles outstanding penalties.
- **`sp_monthly_borrow_summary(p_year)`**: Aggregates monthly borrowings, returns, unique borrowers, and fine revenues.

### Triggers
- **`trg_loans_before_insert`**: Enforces business rules (available copy status, max 3 loans, active student status, zero overdue books, zero unpaid fines).
- **`trg_loans_after_insert`**: Marks physical copy status as `'borrowed'`.
- **`trg_loans_after_update`**: Marks physical copy status as `'available'` upon return.

### Views
- **`vw_book_catalog`**: Pre-aggregates book metadata, authors list (`GROUP_CONCAT`), and copy availability counts.
- **`vw_loan_details`**: Comprehensive loan records with borrower details, calculated overdue days, and fine estimates.
- **`vw_member_unpaid_fines`**: Delinquent member balances grouped by student.
- **`vw_most_borrowed_books`**: Title borrowing frequency rankings.

---

## 🚀 Quick Setup & Installation Guide

### Prerequisites
1. **XAMPP** (Apache & MySQL / MariaDB installed and running).
2. **Python 3.10+** (verified with Python 3.14).

### Step 1: Clone Repository & Setup Virtual Environment
```bash
cd D:\Library-Management-System

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Command Prompt:
.\venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Initialize Database (MariaDB / MySQL)
1. Start **MySQL** in your XAMPP Control Panel.
2. Import the database script (`sql/library_db.sql`):
   - **Via Terminal:**
     ```bash
     D:\xampp\mysql\bin\mysql.exe -u root < sql\library_db.sql
     ```
   - **Or via phpMyAdmin:**
     Open `http://localhost/phpmyadmin` -> Click **Import** -> Select `sql/library_db.sql` -> Click **Go**.

### Step 3: Run the Web Application
```bash
python run.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🔑 Demo Login Credentials

| Role | Username | Password | Notes / Permissions |
|---|---|---|---|
| **Librarian (Admin)** | `admin` | `admin123` | Full administrative, catalog, circulation & report privileges |
| **Librarian (Staff)** | `jdelacruz` | `admin123` | Circulation desk librarian |
| **Member (Good Standing)** | `ana.reyes` | `member123` | Active student with 2 active book loans |
| **Member (Overdue Loan)** | `mark.garcia` | `member123` | 1 overdue loan (borrowing blocked by trigger) |
| **Member (Unpaid Fine)** | `liza.mendoza` | `member123` | ₱15.00 unpaid fine (borrowing blocked by trigger) |
| **Member (Deactivated)** | `kevin.ramos` | `member123` | Deactivated student account (login blocked) |

*(Note: All registered student accounts use the default password `member123`)*

---

## 🧪 Running Automated Unit & Integration Tests

An automated test suite verifying all authentication, CRUD, triggers, stored procedures, and reports is included:

```bash
# Run all unit and integration tests
.\venv\Scripts\python.exe tests\test_full_system.py
```

---

## 📂 Project Directory Structure

```text
D:\Library-Management-System\
├── app\
│   ├── __init__.py           # Application factory, error handlers & context processor
│   ├── db.py                 # Parameterized MySQL database connector & SP helpers
│   ├── routes\
│   │   ├── auth.py           # Authentication, session, password change & RBAC
│   │   ├── books.py          # Books & physical copy inventory manager
│   │   ├── categories.py     # Category classifications & integrity checks
│   │   ├── authors.py        # Author management & junction table linking
│   │   ├── members.py        # Student member CRUD & self-service portal
│   │   ├── loans.py          # Circulation: issue (SP), return (SP) & fines
│   │   ├── dashboard.py      # Librarian & student dashboards with Chart.js
│   │   └── reports.py        # Reports module with print layouts
│   ├── static\
│   │   ├── css\style.css     # Responsive theme & print styles
│   │   └── js\main.js        # UI toggles & confirmation dialogs
│   └── templates\
│       ├── base.html         # Master layout template (Bootstrap 5.3 + Icons)
│       ├── partials\         # Reusable navigation & sidebar components
│       ├── auth\             # Login and Change Password pages
│       ├── books\            # Book catalog, add/edit form, copy details, browse
│       ├── categories\       # Category list and modal forms
│       ├── authors\          # Author list and modal forms
│       ├── members\          # Member directory, student profile, my loans, my fines
│       ├── loans\            # Loans list, check out, quick return, fine collections
│       ├── dashboard\        # Librarian and Student portal dashboards
│       ├── reports\          # Reports hub, most borrowed, overdue, unpaid, monthly summary
│       └── errors\           # 403, 404, 500 error pages
├── sql\
│   └── library_db.sql        # Complete 3NF DB schema, triggers, views, SPs & sample data
├── tests\
│   └── test_full_system.py   # E2E integration test suite
├── .env                      # Local environment configurations
├── .env.example              # Template environment config
├── .gitignore                # Git ignore rules
├── config.py                 # Application configuration settings
├── requirements.txt          # Python dependencies manifest
└── run.py                    # Application entry point
```

---

## 📄 License
Academic Case Study for Database 2 (IT31A). Open source for educational demonstration.
