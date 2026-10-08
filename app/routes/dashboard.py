from datetime import datetime
from flask import Blueprint, render_template, session
from app.routes.auth import librarian_required, member_required
from app.db import query_all, query_one, call_proc

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/librarian')
@librarian_required
def librarian_dashboard():
    current_year = datetime.now().year

    # Summary metric counts
    stats = {
        'total_books': query_one("SELECT COUNT(*) AS total FROM books WHERE is_archived = 0")['total'],
        'total_copies': query_one("SELECT COUNT(*) AS total FROM book_copies")['total'],
        'available_copies': query_one("SELECT COUNT(*) AS total FROM book_copies WHERE status = 'available'")['total'],
        'active_loans': query_one("SELECT COUNT(*) AS total FROM loans WHERE returned_at IS NULL")['total'],
        'overdue_loans': query_one("SELECT COUNT(*) AS total FROM loans WHERE returned_at IS NULL AND due_date < CURDATE()")['total'],
        'total_members': query_one("SELECT COUNT(*) AS total FROM members m JOIN users u ON u.user_id = m.user_id WHERE u.is_active = 1")['total'],
        'unpaid_fines': query_one("SELECT COALESCE(SUM(amount), 0) AS total FROM fines WHERE is_paid = 0")['total']
    }

    # Chart.js data: Call Stored Procedure sp_monthly_borrow_summary
    monthly_data = call_proc('sp_monthly_borrow_summary', (current_year,))
    chart_months = []
    chart_borrowed = []
    chart_returned = []

    if monthly_data and monthly_data[0]:
        for row in monthly_data[0]:
            chart_months.append(row['month_name'])
            chart_borrowed.append(int(row['total_borrowed']))
            chart_returned.append(int(row['total_returned']))

    # Recent 5 loans
    recent_loans = query_all("SELECT * FROM vw_loan_details ORDER BY borrowed_at DESC LIMIT 5")

    # Overdue loans alert list
    overdue_loans = query_all("SELECT * FROM vw_loan_details WHERE loan_status = 'overdue' ORDER BY due_date ASC LIMIT 5")

    return render_template(
        'dashboard/librarian.html',
        stats=stats,
        current_year=current_year,
        chart_months=chart_months,
        chart_borrowed=chart_borrowed,
        chart_returned=chart_returned,
        recent_loans=recent_loans,
        overdue_loans=overdue_loans
    )


@dashboard_bp.route('/member')
@member_required
def member_dashboard():
    member_id = session.get('member_id')
    if not member_id:
        return render_template('dashboard/member.html', member=None, active_loans=[], stats={})

    member = query_one("""
        SELECT m.*, u.first_name, u.last_name, u.email, c.course_code, c.course_name
        FROM members m
        JOIN users u ON u.user_id = m.user_id
        JOIN courses c ON c.course_id = m.course_id
        WHERE m.member_id = %s
    """, (member_id,))

    # Active loans for current student
    active_loans = query_all(
        "SELECT * FROM vw_loan_details WHERE member_id = %s AND returned_at IS NULL ORDER BY due_date ASC",
        (member_id,)
    )

    # Lifetime stats for student
    stats = {
        'active_count': len(active_loans),
        'max_limit': 3,
        'overdue_count': sum(1 for l in active_loans if l['loan_status'] == 'overdue'),
        'unpaid_fines': query_one("""
            SELECT COALESCE(SUM(f.amount), 0) AS total 
            FROM fines f JOIN loans l ON l.loan_id = f.loan_id 
            WHERE l.member_id = %s AND f.is_paid = 0
        """, (member_id,))['total']
    }

    # Recommended / Newly Added Books for student
    recent_books = query_all("SELECT * FROM vw_book_catalog WHERE is_archived = 0 ORDER BY book_id DESC LIMIT 4")

    return render_template(
        'dashboard/member.html',
        member=member,
        active_loans=active_loans,
        stats=stats,
        recent_books=recent_books
    )
