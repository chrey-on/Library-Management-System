from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import pymysql
from app.routes.auth import librarian_required
from app.db import query_all, query_one, call_proc, get_db

loans_bp = Blueprint('loans', __name__, url_prefix='/loans')

@loans_bp.route('/', methods=['GET'])
@librarian_required
def list_loans():
    status_filter = request.args.get('status', 'active')  # 'all', 'active', 'overdue', 'returned'
    q = request.args.get('q', '').strip()

    sql = "SELECT * FROM vw_loan_details WHERE 1=1"
    params = []

    if status_filter == 'active':
        sql += " AND loan_status IN ('borrowed', 'overdue')"
    elif status_filter == 'overdue':
        sql += " AND loan_status = 'overdue'"
    elif status_filter == 'returned':
        sql += " AND loan_status = 'returned'"

    if q:
        sql += " AND (title LIKE %s OR accession_no LIKE %s OR student_no LIKE %s OR member_name LIKE %s)"
        like_term = f"%{q}%"
        params.extend([like_term, like_term, like_term, like_term])

    sql += " ORDER BY borrowed_at DESC"
    loans = query_all(sql, params)

    # Statistics for summary badges
    stats = {
        'active': query_one("SELECT COUNT(*) AS total FROM loans WHERE returned_at IS NULL")['total'],
        'overdue': query_one("SELECT COUNT(*) AS total FROM loans WHERE returned_at IS NULL AND due_date < CURDATE()")['total'],
        'returned': query_one("SELECT COUNT(*) AS total FROM loans WHERE returned_at IS NOT NULL")['total']
    }

    return render_template('loans/list.html', loans=loans, status_filter=status_filter, q=q, stats=stats)


@loans_bp.route('/issue', methods=['GET', 'POST'])
@librarian_required
def issue_loan():
    if request.method == 'POST':
        member_id = request.form.get('member_id')
        copy_id = request.form.get('copy_id')
        librarian_id = session.get('user_id')

        if not member_id or not copy_id:
            flash('Please select both a student member and a book copy.', 'danger')
            return redirect(url_for('loans.issue_loan'))

        try:
            # Call Stored Procedure sp_borrow_book
            # (Triggers inside MariaDB will enforce active status, fine blocks, max 3 loan limits, and copy availability)
            result = call_proc('sp_borrow_book', (int(member_id), int(copy_id), int(librarian_id)))
            
            # Fetch copy details for confirmation message
            copy = query_one(
                "SELECT bc.accession_no, b.title FROM book_copies bc JOIN books b ON b.book_id = bc.book_id WHERE bc.copy_id = %s",
                (copy_id,)
            )
            member = query_one(
                "SELECT u.first_name, u.last_name, m.student_no FROM members m JOIN users u ON u.user_id = m.user_id WHERE m.member_id = %s",
                (member_id,)
            )
            
            due_date_str = result[0][0]['due_date'].strftime('%b %d, %Y') if result and result[0] else 'in 7 days'
            flash(
                f'Successfully issued "{copy["title"]}" ({copy["accession_no"]}) to {member["first_name"]} {member["last_name"]} ({member["student_no"]}). Due Date: {due_date_str}.',
                'success'
            )
            return redirect(url_for('loans.list_loans'))
            
        except pymysql.MySQLError as e:
            # Capture custom error messages from MariaDB triggers (e.g. Signal 45000)
            error_msg = str(e)
            if len(e.args) > 1:
                error_msg = e.args[1]
            flash(f'Borrowing Blocked: {error_msg}', 'danger')

    # Load active student members and available physical book copies for selection
    members = query_all("""
        SELECT 
            m.member_id, m.student_no, u.first_name, u.last_name, c.course_code,
            (SELECT COUNT(*) FROM loans l WHERE l.member_id = m.member_id AND l.returned_at IS NULL) AS active_loans,
            (SELECT COUNT(*) FROM fines f JOIN loans l ON l.loan_id = f.loan_id WHERE l.member_id = m.member_id AND f.is_paid = 0) AS unpaid_fines_count
        FROM members m
        JOIN users u ON u.user_id = m.user_id
        JOIN courses c ON c.course_id = m.course_id
        WHERE u.is_active = 1
        ORDER BY u.last_name ASC, u.first_name ASC
    """)

    available_copies = query_all("""
        SELECT bc.copy_id, bc.accession_no, b.title, b.isbn, cat.name AS category_name
        FROM book_copies bc
        JOIN books b ON b.book_id = bc.book_id
        JOIN categories cat ON cat.category_id = b.category_id
        WHERE bc.status = 'available' AND b.is_archived = 0
        ORDER BY b.title ASC, bc.accession_no ASC
    """)

    preselected_member_id = request.args.get('member_id', '')
    preselected_copy_id = request.args.get('copy_id', '')

    return render_template(
        'loans/issue.html',
        members=members,
        available_copies=available_copies,
        preselected_member_id=preselected_member_id,
        preselected_copy_id=preselected_copy_id
    )


@loans_bp.route('/return', methods=['GET', 'POST'])
@librarian_required
def return_loan():
    if request.method == 'POST':
        loan_id = request.form.get('loan_id')
        accession_no = request.form.get('accession_no', '').strip()
        librarian_id = session.get('user_id')

        # Allow returning either by selecting a loan_id or typing an accession number
        if not loan_id and accession_no:
            active_loan = query_one("""
                SELECT l.loan_id FROM loans l
                JOIN book_copies bc ON bc.copy_id = l.copy_id
                WHERE bc.accession_no = %s AND l.returned_at IS NULL
            """, (accession_no,))
            if active_loan:
                loan_id = active_loan['loan_id']
            else:
                flash(f'No active loan found for accession number "{accession_no}".', 'warning')
                return redirect(url_for('loans.return_loan'))

        if not loan_id:
            flash('Please select or specify an active book loan to return.', 'danger')
            return redirect(url_for('loans.return_loan'))

        try:
            # Call Stored Procedure sp_return_book
            res = call_proc('sp_return_book', (int(loan_id), int(librarian_id)))
            
            # Fetch returned details
            loan_info = query_one("""
                SELECT b.title, bc.accession_no, CONCAT(u.first_name, ' ', u.last_name) AS member_name
                FROM loans l
                JOIN book_copies bc ON bc.copy_id = l.copy_id
                JOIN books b ON b.book_id = bc.book_id
                JOIN members m ON m.member_id = l.member_id
                JOIN users u ON u.user_id = m.user_id
                WHERE l.loan_id = %s
            """, (loan_id,))

            days_overdue = 0
            fine_amount = 0.0
            if res and res[0]:
                days_overdue = res[0][0].get('days_overdue', 0)
                fine_amount = float(res[0][0].get('fine_amount', 0.0))

            if days_overdue > 0 and fine_amount > 0:
                flash(
                    f'Book "{loan_info["title"]}" ({loan_info["accession_no"]}) returned by {loan_info["member_name"]}. '
                    f'OVERDUE by {days_overdue} day(s). A fine of ₱{fine_amount:.2f} has been assessed.',
                    'warning'
                )
            else:
                flash(
                    f'Book "{loan_info["title"]}" ({loan_info["accession_no"]}) returned on time by {loan_info["member_name"]}. Copy is now available.',
                    'success'
                )
            return redirect(url_for('loans.list_loans'))

        except pymysql.MySQLError as e:
            error_msg = str(e)
            if len(e.args) > 1:
                error_msg = e.args[1]
            flash(f'Return Failed: {error_msg}', 'danger')

    # Load active loans list for quick selection
    active_loans = query_all("SELECT * FROM vw_loan_details WHERE loan_status IN ('borrowed', 'overdue') ORDER BY due_date ASC")
    return render_template('loans/return.html', active_loans=active_loans)


@loans_bp.route('/fines', methods=['GET'])
@librarian_required
def list_fines():
    status_filter = request.args.get('status', 'unpaid')  # 'unpaid', 'paid', 'all'
    q = request.args.get('q', '').strip()

    sql = """
        SELECT 
            f.fine_id,
            f.loan_id,
            f.days_overdue,
            f.rate_per_day,
            f.amount,
            f.is_paid,
            f.paid_at,
            f.created_at,
            l.borrowed_at,
            l.due_date,
            l.returned_at,
            b.title,
            b.isbn,
            bc.accession_no,
            m.member_id,
            m.student_no,
            CONCAT(u.first_name, ' ', u.last_name) AS member_name,
            u.email,
            CONCAT(rec.first_name, ' ', rec.last_name) AS received_by_name
        FROM fines f
        JOIN loans l ON l.loan_id = f.loan_id
        JOIN book_copies bc ON bc.copy_id = l.copy_id
        JOIN books b ON b.book_id = bc.book_id
        JOIN members m ON m.member_id = l.member_id
        JOIN users u ON u.user_id = m.user_id
        LEFT JOIN users rec ON rec.user_id = f.received_by
        WHERE 1=1
    """
    params = []

    if status_filter == 'unpaid':
        sql += " AND f.is_paid = 0"
    elif status_filter == 'paid':
        sql += " AND f.is_paid = 1"

    if q:
        sql += " AND (m.student_no LIKE %s OR u.first_name LIKE %s OR u.last_name LIKE %s OR b.title LIKE %s OR bc.accession_no LIKE %s)"
        like_term = f"%{q}%"
        params.extend([like_term, like_term, like_term, like_term, like_term])

    sql += " ORDER BY f.created_at DESC"
    fines = query_all(sql, params)

    # Outstanding balances grouped by member
    member_balances = query_all("SELECT * FROM vw_member_unpaid_fines ORDER BY total_unpaid DESC")

    stats = {
        'total_unpaid': query_one("SELECT COALESCE(SUM(amount), 0) AS total FROM fines WHERE is_paid = 0")['total'],
        'total_collected': query_one("SELECT COALESCE(SUM(amount), 0) AS total FROM fines WHERE is_paid = 1")['total'],
        'unpaid_count': query_one("SELECT COUNT(*) AS total FROM fines WHERE is_paid = 0")['total']
    }

    return render_template(
        'loans/fines.html',
        fines=fines,
        member_balances=member_balances,
        status_filter=status_filter,
        q=q,
        stats=stats
    )


@loans_bp.route('/fines/pay/<int:fine_id>', methods=['POST'])
@librarian_required
def pay_fine(fine_id):
    librarian_id = session.get('user_id')
    try:
        call_proc('sp_pay_fine', (fine_id, librarian_id))
        flash('Fine marked as PAID successfully. Member records updated.', 'success')
    except pymysql.MySQLError as e:
        error_msg = str(e)
        if len(e.args) > 1:
            error_msg = e.args[1]
        flash(f'Payment processing error: {error_msg}', 'danger')

    return redirect(url_for('loans.list_fines'))
