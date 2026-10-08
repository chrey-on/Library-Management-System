from datetime import datetime
from flask import Blueprint, render_template, request
from app.routes.auth import librarian_required
from app.db import query_all, query_one, call_proc

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/', methods=['GET'])
@librarian_required
def reports_home():
    current_year = datetime.now().year
    
    # Overview counts for the report dashboard hub
    stats = {
        'total_loans': query_one("SELECT COUNT(*) AS total FROM loans")['total'],
        'overdue_count': query_one("SELECT COUNT(*) AS total FROM loans WHERE returned_at IS NULL AND due_date < CURDATE()")['total'],
        'unpaid_fines_total': query_one("SELECT COALESCE(SUM(amount), 0) AS total FROM fines WHERE is_paid = 0")['total'],
        'total_fines_collected': query_one("SELECT COALESCE(SUM(amount), 0) AS total FROM fines WHERE is_paid = 1")['total']
    }
    return render_template('reports/index.html', stats=stats, current_year=current_year)


@reports_bp.route('/most-borrowed', methods=['GET'])
@librarian_required
def most_borrowed():
    # Fetch top borrowed books from the view vw_most_borrowed_books
    books = query_all("""
        SELECT 
            b.*,
            (SELECT GROUP_CONCAT(CONCAT(a.first_name, ' ', a.last_name) SEPARATOR ', ')
             FROM book_authors ba JOIN authors a ON a.author_id = ba.author_id WHERE ba.book_id = b.book_id) AS authors
        FROM vw_most_borrowed_books b
        ORDER BY b.times_borrowed DESC, b.title ASC
    """)
    return render_template('reports/most_borrowed.html', books=books)


@reports_bp.route('/overdue', methods=['GET'])
@librarian_required
def overdue_report():
    # Fetch overdue loans with member contact numbers for immediate follow-up
    overdue_loans = query_all("""
        SELECT 
            l.loan_id, l.copy_id, bc.accession_no, b.title, b.isbn,
            m.student_no, CONCAT(u.first_name, ' ', u.last_name) AS member_name,
            u.email, m.contact_no, c.course_code,
            l.borrowed_at, l.due_date,
            DATEDIFF(CURDATE(), l.due_date) AS days_overdue,
            DATEDIFF(CURDATE(), l.due_date) * (SELECT CAST(setting_value AS DECIMAL(8,2)) FROM library_settings WHERE setting_key = 'fine_per_day') AS estimated_fine
        FROM loans l
        JOIN book_copies bc ON bc.copy_id = l.copy_id
        JOIN books b ON b.book_id = bc.book_id
        JOIN members m ON m.member_id = l.member_id
        JOIN users u ON u.user_id = m.user_id
        JOIN courses c ON c.course_id = m.course_id
        WHERE l.returned_at IS NULL AND l.due_date < CURDATE()
        ORDER BY days_overdue DESC, l.due_date ASC
    """)
    total_est_fines = sum(row['estimated_fine'] for row in overdue_loans)
    return render_template('reports/overdue.html', overdue_loans=overdue_loans, total_est_fines=total_est_fines)


@reports_bp.route('/unpaid-fines', methods=['GET'])
@librarian_required
def unpaid_fines():
    # Fetch members with unpaid fines using the view vw_member_unpaid_fines
    unpaid_members = query_all("""
        SELECT uf.*, c.course_code, m.contact_no
        FROM vw_member_unpaid_fines uf
        JOIN members m ON m.member_id = uf.member_id
        JOIN courses c ON c.course_id = m.course_id
        ORDER BY uf.total_unpaid DESC
    """)
    total_unpaid_sum = sum(m['total_unpaid'] for m in unpaid_members)
    return render_template('reports/unpaid_fines.html', unpaid_members=unpaid_members, total_unpaid_sum=total_unpaid_sum)


@reports_bp.route('/monthly-summary', methods=['GET'])
@librarian_required
def monthly_summary():
    year = request.args.get('year', datetime.now().year)
    try:
        year = int(year)
    except ValueError:
        year = datetime.now().year

    # Call Stored Procedure sp_monthly_borrow_summary
    res = call_proc('sp_monthly_borrow_summary', (year,))
    monthly_rows = res[0] if res and res[0] else []

    # Chart arrays
    chart_months = [row['month_name'] for row in monthly_rows]
    chart_borrowed = [int(row['total_borrowed']) for row in monthly_rows]
    chart_returned = [int(row['total_returned']) for row in monthly_rows]
    chart_fines = [float(row['fines_assessed']) for row in monthly_rows]

    totals = {
        'total_borrowed': sum(row['total_borrowed'] for row in monthly_rows),
        'total_returned': sum(row['total_returned'] for row in monthly_rows),
        'total_fines': sum(float(row['fines_assessed']) for row in monthly_rows)
    }

    # Available years list for filter
    available_years = [datetime.now().year - i for i in range(5)]

    return render_template(
        'reports/monthly_summary.html',
        monthly_rows=monthly_rows,
        year=year,
        totals=totals,
        available_years=available_years,
        chart_months=chart_months,
        chart_borrowed=chart_borrowed,
        chart_returned=chart_returned,
        chart_fines=chart_fines
    )
