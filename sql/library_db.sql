-- =====================================================================
--  LIBRARY MANAGEMENT SYSTEM - DATABASE SCRIPT
--  Database 2 Case Study (IT31A)
--  Target: MariaDB 10.4 (XAMPP) / MySQL 8 compatible
--
--  HOW TO RUN:
--    Option A (phpMyAdmin): Import tab -> choose this file -> Go
--    Option B (terminal):   D:\xampp\mysql\bin\mysql.exe -u root < sql\library_db.sql
--
--  WARNING: This script DROPS and recreates the `library_db` database.
--           Re-running it resets ALL data back to the sample data.
--
--  SAMPLE LOGINS:
--    Librarian -> username: admin       password: admin123
--    Member    -> username: ana.reyes   password: member123
--    (all sample members use the password: member123)
-- =====================================================================

DROP DATABASE IF EXISTS library_db;
CREATE DATABASE library_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE library_db;


-- =====================================================================
--  SECTION 1: TABLES
-- =====================================================================

-- ---------------------------------------------------------------------
-- library_settings: configurable business rules (no hard-coded values)
-- ---------------------------------------------------------------------
CREATE TABLE library_settings (
    setting_key    VARCHAR(50)  NOT NULL,
    setting_value  VARCHAR(100) NOT NULL,
    description    VARCHAR(255) NULL,
    CONSTRAINT pk_library_settings PRIMARY KEY (setting_key)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- users: login accounts for BOTH librarians and members
-- ---------------------------------------------------------------------
CREATE TABLE users (
    user_id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
    username       VARCHAR(50)  NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,            -- werkzeug pbkdf2 hash
    role           ENUM('librarian', 'member') NOT NULL,
    first_name     VARCHAR(50)  NOT NULL,
    last_name      VARCHAR(50)  NOT NULL,
    email          VARCHAR(100) NOT NULL,
    is_active      TINYINT(1)   NOT NULL DEFAULT 1,  -- 0 = deactivated
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT pk_users          PRIMARY KEY (user_id),
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email    UNIQUE (email),
    CONSTRAINT chk_users_active  CHECK (is_active IN (0, 1)),
    INDEX idx_users_role (role),
    INDEX idx_users_name (last_name, first_name)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- courses: lookup table (keeps course names out of members -> 3NF)
-- ---------------------------------------------------------------------
CREATE TABLE courses (
    course_id    INT UNSIGNED NOT NULL AUTO_INCREMENT,
    course_code  VARCHAR(20)  NOT NULL,
    course_name  VARCHAR(100) NOT NULL,
    CONSTRAINT pk_courses      PRIMARY KEY (course_id),
    CONSTRAINT uq_courses_code UNIQUE (course_code)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- members: student-specific details (1-to-1 with users)
-- ---------------------------------------------------------------------
CREATE TABLE members (
    member_id    INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    user_id      INT UNSIGNED     NOT NULL,
    student_no   VARCHAR(20)      NOT NULL,
    course_id    INT UNSIGNED     NOT NULL,
    year_level   TINYINT UNSIGNED NOT NULL,
    contact_no   VARCHAR(20)      NULL,
    CONSTRAINT pk_members            PRIMARY KEY (member_id),
    CONSTRAINT uq_members_user       UNIQUE (user_id),
    CONSTRAINT uq_members_student_no UNIQUE (student_no),
    CONSTRAINT chk_members_year      CHECK (year_level BETWEEN 1 AND 5),
    CONSTRAINT fk_members_user   FOREIGN KEY (user_id)
        REFERENCES users (user_id)     ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_members_course FOREIGN KEY (course_id)
        REFERENCES courses (course_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- categories
-- ---------------------------------------------------------------------
CREATE TABLE categories (
    category_id  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name         VARCHAR(50)  NOT NULL,
    description  VARCHAR(255) NULL,
    CONSTRAINT pk_categories      PRIMARY KEY (category_id),
    CONSTRAINT uq_categories_name UNIQUE (name)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- authors
-- ---------------------------------------------------------------------
CREATE TABLE authors (
    author_id   INT UNSIGNED NOT NULL AUTO_INCREMENT,
    first_name  VARCHAR(50)  NOT NULL,
    last_name   VARCHAR(50)  NOT NULL,
    CONSTRAINT pk_authors PRIMARY KEY (author_id),
    INDEX idx_authors_name (last_name, first_name)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- books: the title/edition (NOT the physical copy)
-- ---------------------------------------------------------------------
CREATE TABLE books (
    book_id           INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    isbn              VARCHAR(17)       NOT NULL,
    title             VARCHAR(200)      NOT NULL,
    category_id       INT UNSIGNED      NOT NULL,
    publisher         VARCHAR(100)      NULL,
    publication_year  SMALLINT UNSIGNED NULL,
    description       TEXT              NULL,
    is_archived       TINYINT(1)        NOT NULL DEFAULT 0,  -- soft delete
    created_at        DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT pk_books          PRIMARY KEY (book_id),
    CONSTRAINT uq_books_isbn     UNIQUE (isbn),
    CONSTRAINT chk_books_year    CHECK (publication_year IS NULL
                                        OR publication_year BETWEEN 1450 AND 2100),
    CONSTRAINT chk_books_archived CHECK (is_archived IN (0, 1)),
    CONSTRAINT fk_books_category FOREIGN KEY (category_id)
        REFERENCES categories (category_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_books_title (title),
    INDEX idx_books_archived (is_archived)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- book_authors: junction table (many-to-many books <-> authors)
-- ---------------------------------------------------------------------
CREATE TABLE book_authors (
    book_id    INT UNSIGNED NOT NULL,
    author_id  INT UNSIGNED NOT NULL,
    CONSTRAINT pk_book_authors PRIMARY KEY (book_id, author_id),
    CONSTRAINT fk_book_authors_book   FOREIGN KEY (book_id)
        REFERENCES books (book_id)     ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_book_authors_author FOREIGN KEY (author_id)
        REFERENCES authors (author_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_book_authors_author (author_id)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- book_copies: each physical copy on the shelf
-- ---------------------------------------------------------------------
CREATE TABLE book_copies (
    copy_id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
    book_id        INT UNSIGNED NOT NULL,
    accession_no   VARCHAR(20)  NOT NULL,
    status         ENUM('available', 'borrowed', 'lost', 'damaged')
                                NOT NULL DEFAULT 'available',
    acquired_date  DATE         NULL,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_book_copies           PRIMARY KEY (copy_id),
    CONSTRAINT uq_book_copies_accession UNIQUE (accession_no),
    CONSTRAINT fk_book_copies_book FOREIGN KEY (book_id)
        REFERENCES books (book_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_book_copies_book_status (book_id, status)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- loans: one row per borrow transaction
-- ---------------------------------------------------------------------
CREATE TABLE loans (
    loan_id      INT UNSIGNED NOT NULL AUTO_INCREMENT,
    copy_id      INT UNSIGNED NOT NULL,
    member_id    INT UNSIGNED NOT NULL,
    issued_by    INT UNSIGNED NOT NULL,          -- librarian who lent it
    borrowed_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    due_date     DATE         NOT NULL,
    returned_at  DATETIME     NULL,              -- NULL = still borrowed
    received_by  INT UNSIGNED NULL,              -- librarian who received it
    -- Helper column: holds copy_id ONLY while the loan is active.
    -- The UNIQUE key below makes it IMPOSSIBLE (at the database level)
    -- for the same copy to have two active loans at the same time.
    active_copy_id INT UNSIGNED AS (IF(returned_at IS NULL, copy_id, NULL)) PERSISTENT,
    CONSTRAINT pk_loans             PRIMARY KEY (loan_id),
    CONSTRAINT uq_loans_active_copy UNIQUE (active_copy_id),
    CONSTRAINT chk_loans_due        CHECK (due_date >= DATE(borrowed_at)),
    CONSTRAINT chk_loans_returned   CHECK (returned_at IS NULL OR returned_at >= borrowed_at),
    CONSTRAINT fk_loans_copy        FOREIGN KEY (copy_id)
        REFERENCES book_copies (copy_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_loans_member      FOREIGN KEY (member_id)
        REFERENCES members (member_id)   ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_loans_issued_by   FOREIGN KEY (issued_by)
        REFERENCES users (user_id)       ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_loans_received_by FOREIGN KEY (received_by)
        REFERENCES users (user_id)       ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_loans_member_returned (member_id, returned_at),
    INDEX idx_loans_due_date (due_date),
    INDEX idx_loans_borrowed_at (borrowed_at)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- fines: at most one fine per loan (created when returned late)
-- ---------------------------------------------------------------------
CREATE TABLE fines (
    fine_id       INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    loan_id       INT UNSIGNED  NOT NULL,
    days_overdue  INT UNSIGNED  NOT NULL,
    rate_per_day  DECIMAL(8,2)  NOT NULL,        -- rate at the time of the fine
    -- amount is computed automatically, never typed in manually
    amount        DECIMAL(10,2) AS (days_overdue * rate_per_day) PERSISTENT,
    is_paid       TINYINT(1)    NOT NULL DEFAULT 0,
    paid_at       DATETIME      NULL,
    received_by   INT UNSIGNED  NULL,            -- librarian who received payment
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fines          PRIMARY KEY (fine_id),
    CONSTRAINT uq_fines_loan     UNIQUE (loan_id),
    CONSTRAINT chk_fines_days    CHECK (days_overdue > 0),
    CONSTRAINT chk_fines_rate    CHECK (rate_per_day >= 0),
    CONSTRAINT chk_fines_paid    CHECK ((is_paid = 0 AND paid_at IS NULL)
                                     OR (is_paid = 1 AND paid_at IS NOT NULL)),
    CONSTRAINT fk_fines_loan     FOREIGN KEY (loan_id)
        REFERENCES loans (loan_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_fines_received FOREIGN KEY (received_by)
        REFERENCES users (user_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_fines_is_paid (is_paid)
) ENGINE = InnoDB;


-- =====================================================================
--  SECTION 2: TRIGGERS
-- =====================================================================
DELIMITER $$

-- ---------------------------------------------------------------------
-- trg_loans_before_insert
-- Enforces ALL borrowing rules inside the database, so they cannot be
-- bypassed even if someone inserts directly into the loans table.
-- Only checks NEW loans (returned_at IS NULL), not historical records.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_loans_before_insert
BEFORE INSERT ON loans
FOR EACH ROW
BEGIN
    DECLARE v_copy_status  VARCHAR(20);
    DECLARE v_archived     TINYINT;
    DECLARE v_is_active    TINYINT;
    DECLARE v_max_loans    INT;
    DECLARE v_active_loans INT;
    DECLARE v_msg          VARCHAR(255);

    IF NEW.returned_at IS NULL THEN

        -- Rule 1: the copy must exist and be available
        SET v_copy_status = (SELECT status FROM book_copies
                             WHERE copy_id = NEW.copy_id);
        IF v_copy_status IS NULL THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Book copy not found.';
        ELSEIF v_copy_status <> 'available' THEN
            SET v_msg = CONCAT('This copy is not available (status: ', v_copy_status, ').');
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
        END IF;

        -- Rule 2: the book must not be archived
        SET v_archived = (SELECT b.is_archived
                          FROM book_copies bc
                          JOIN books b ON b.book_id = bc.book_id
                          WHERE bc.copy_id = NEW.copy_id);
        IF v_archived = 1 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This book is archived and cannot be borrowed.';
        END IF;

        -- Rule 3: the member must exist and be active
        SET v_is_active = (SELECT u.is_active
                           FROM members m
                           JOIN users u ON u.user_id = m.user_id
                           WHERE m.member_id = NEW.member_id);
        IF v_is_active IS NULL THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Member not found.';
        ELSEIF v_is_active = 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Member account is deactivated.';
        END IF;

        -- Rule 4: no overdue books still out
        IF EXISTS (SELECT 1 FROM loans
                   WHERE member_id = NEW.member_id
                     AND returned_at IS NULL
                     AND due_date < CURDATE()) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Member has an overdue book. It must be returned first.';
        END IF;

        -- Rule 5: no unpaid fines
        IF EXISTS (SELECT 1 FROM fines f
                   JOIN loans l ON l.loan_id = f.loan_id
                   WHERE l.member_id = NEW.member_id
                     AND f.is_paid = 0) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Member has unpaid fines. Please settle them first.';
        END IF;

        -- Rule 6: maximum active loans (from library_settings)
        SET v_max_loans = (SELECT CAST(setting_value AS UNSIGNED)
                           FROM library_settings
                           WHERE setting_key = 'max_active_loans');
        SET v_active_loans = (SELECT COUNT(*) FROM loans
                              WHERE member_id = NEW.member_id
                                AND returned_at IS NULL);
        IF v_active_loans >= v_max_loans THEN
            SET v_msg = CONCAT('Member has reached the maximum of ', v_max_loans, ' active loans.');
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
        END IF;

    END IF;
END$$

-- ---------------------------------------------------------------------
-- trg_loans_after_insert: mark the copy as borrowed
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_loans_after_insert
AFTER INSERT ON loans
FOR EACH ROW
BEGIN
    IF NEW.returned_at IS NULL THEN
        UPDATE book_copies SET status = 'borrowed' WHERE copy_id = NEW.copy_id;
    END IF;
END$$

-- ---------------------------------------------------------------------
-- trg_loans_after_update: mark the copy as available when returned
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_loans_after_update
AFTER UPDATE ON loans
FOR EACH ROW
BEGIN
    IF OLD.returned_at IS NULL AND NEW.returned_at IS NOT NULL THEN
        UPDATE book_copies
        SET status = 'available'
        WHERE copy_id = NEW.copy_id AND status = 'borrowed';
    END IF;
END$$

DELIMITER ;


-- =====================================================================
--  SECTION 3: VIEWS
-- =====================================================================

-- ---------------------------------------------------------------------
-- vw_book_catalog: books with category, author list, and copy counts
-- ---------------------------------------------------------------------
CREATE VIEW vw_book_catalog AS
SELECT
    b.book_id,
    b.isbn,
    b.title,
    b.category_id,
    c.name AS category_name,
    b.publisher,
    b.publication_year,
    b.is_archived,
    (SELECT GROUP_CONCAT(CONCAT(a.first_name, ' ', a.last_name)
                         ORDER BY a.last_name SEPARATOR ', ')
       FROM book_authors ba
       JOIN authors a ON a.author_id = ba.author_id
      WHERE ba.book_id = b.book_id)                          AS authors,
    (SELECT COUNT(*) FROM book_copies bc
      WHERE bc.book_id = b.book_id)                          AS total_copies,
    (SELECT COUNT(*) FROM book_copies bc
      WHERE bc.book_id = b.book_id AND bc.status = 'available') AS available_copies
FROM books b
JOIN categories c ON c.category_id = b.category_id;

-- ---------------------------------------------------------------------
-- vw_loan_details: every loan with book, member, status, and fine info
-- ---------------------------------------------------------------------
CREATE VIEW vw_loan_details AS
SELECT
    l.loan_id,
    l.copy_id,
    bc.accession_no,
    b.book_id,
    b.isbn,
    b.title,
    l.member_id,
    m.student_no,
    CONCAT(u.first_name, ' ', u.last_name)                AS member_name,
    l.borrowed_at,
    l.due_date,
    l.returned_at,
    CASE
        WHEN l.returned_at IS NOT NULL THEN 'returned'
        WHEN l.due_date < CURDATE()    THEN 'overdue'
        ELSE 'borrowed'
    END                                                   AS loan_status,
    CASE
        WHEN l.returned_at IS NULL AND l.due_date < CURDATE()
            THEN DATEDIFF(CURDATE(), l.due_date)
        ELSE 0
    END                                                   AS current_days_overdue,
    -- live estimate for books that are overdue and still out
    CASE
        WHEN l.returned_at IS NULL AND l.due_date < CURDATE()
            THEN DATEDIFF(CURDATE(), l.due_date)
                 * (SELECT CAST(setting_value AS DECIMAL(8,2))
                      FROM library_settings WHERE setting_key = 'fine_per_day')
        ELSE 0
    END                                                   AS estimated_fine,
    f.fine_id,
    f.amount                                              AS fine_amount,
    f.is_paid                                             AS fine_is_paid,
    l.issued_by,
    l.received_by
FROM loans l
JOIN book_copies bc ON bc.copy_id  = l.copy_id
JOIN books b        ON b.book_id   = bc.book_id
JOIN members m      ON m.member_id = l.member_id
JOIN users u        ON u.user_id   = m.user_id
LEFT JOIN fines f   ON f.loan_id   = l.loan_id;

-- ---------------------------------------------------------------------
-- vw_member_unpaid_fines: total unpaid fines per member
-- ---------------------------------------------------------------------
CREATE VIEW vw_member_unpaid_fines AS
SELECT
    m.member_id,
    m.student_no,
    CONCAT(u.first_name, ' ', u.last_name) AS member_name,
    u.email,
    COUNT(f.fine_id)                       AS unpaid_count,
    SUM(f.amount)                          AS total_unpaid
FROM fines f
JOIN loans l   ON l.loan_id   = f.loan_id
JOIN members m ON m.member_id = l.member_id
JOIN users u   ON u.user_id   = m.user_id
WHERE f.is_paid = 0
GROUP BY m.member_id, m.student_no, u.first_name, u.last_name, u.email;

-- ---------------------------------------------------------------------
-- vw_most_borrowed_books: borrow count per book (for reports)
-- ---------------------------------------------------------------------
CREATE VIEW vw_most_borrowed_books AS
SELECT
    b.book_id,
    b.isbn,
    b.title,
    c.name           AS category_name,
    COUNT(l.loan_id) AS times_borrowed
FROM books b
JOIN categories c        ON c.category_id = b.category_id
LEFT JOIN book_copies bc ON bc.book_id    = b.book_id
LEFT JOIN loans l        ON l.copy_id     = bc.copy_id
GROUP BY b.book_id, b.isbn, b.title, c.name;


-- =====================================================================
--  SECTION 4: STORED PROCEDURES
-- =====================================================================
DELIMITER $$

-- ---------------------------------------------------------------------
-- sp_borrow_book: creates a loan with the due date from settings.
-- All validation happens in trg_loans_before_insert.
-- Returns: one row with the new loan_id and due_date.
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_borrow_book(
    IN p_member_id    INT UNSIGNED,
    IN p_copy_id      INT UNSIGNED,
    IN p_librarian_id INT UNSIGNED
)
BEGIN
    DECLARE v_loan_days INT;
    DECLARE v_due_date  DATE;

    SET v_loan_days = (SELECT CAST(setting_value AS UNSIGNED)
                       FROM library_settings WHERE setting_key = 'loan_days');
    SET v_due_date  = DATE_ADD(CURDATE(), INTERVAL v_loan_days DAY);

    INSERT INTO loans (copy_id, member_id, issued_by, borrowed_at, due_date)
    VALUES (p_copy_id, p_member_id, p_librarian_id, NOW(), v_due_date);

    SELECT LAST_INSERT_ID() AS loan_id, v_due_date AS due_date;
END$$

-- ---------------------------------------------------------------------
-- sp_return_book: marks a loan returned and creates a fine if late.
-- Runs in a transaction: either everything succeeds or nothing changes.
-- Returns: one row with days_overdue and fine_amount.
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_return_book(
    IN p_loan_id      INT UNSIGNED,
    IN p_librarian_id INT UNSIGNED
)
BEGIN
    DECLARE v_due_date    DATE;
    DECLARE v_returned_at DATETIME;
    DECLARE v_days_late   INT DEFAULT 0;
    DECLARE v_rate        DECIMAL(8,2) DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    IF NOT EXISTS (SELECT 1 FROM loans WHERE loan_id = p_loan_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Loan not found.';
    END IF;

    SELECT due_date, returned_at
      INTO v_due_date, v_returned_at
      FROM loans
     WHERE loan_id = p_loan_id
       FOR UPDATE;                       -- lock the row while we work

    IF v_returned_at IS NOT NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This book has already been returned.';
    END IF;

    UPDATE loans
       SET returned_at = NOW(),
           received_by = p_librarian_id
     WHERE loan_id = p_loan_id;          -- trigger sets copy to 'available'

    SET v_days_late = DATEDIFF(CURDATE(), v_due_date);

    IF v_days_late > 0 THEN
        SET v_rate = (SELECT CAST(setting_value AS DECIMAL(8,2))
                      FROM library_settings WHERE setting_key = 'fine_per_day');
        INSERT INTO fines (loan_id, days_overdue, rate_per_day)
        VALUES (p_loan_id, v_days_late, v_rate);
    END IF;

    COMMIT;

    SELECT GREATEST(v_days_late, 0)                        AS days_overdue,
           IF(v_days_late > 0, v_days_late * v_rate, 0.00) AS fine_amount;
END$$

-- ---------------------------------------------------------------------
-- sp_pay_fine: marks a fine as fully paid
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_pay_fine(
    IN p_fine_id      INT UNSIGNED,
    IN p_librarian_id INT UNSIGNED
)
BEGIN
    DECLARE v_is_paid TINYINT;

    SET v_is_paid = (SELECT is_paid FROM fines WHERE fine_id = p_fine_id);

    IF v_is_paid IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Fine not found.';
    ELSEIF v_is_paid = 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This fine is already paid.';
    END IF;

    UPDATE fines
       SET is_paid = 1,
           paid_at = NOW(),
           received_by = p_librarian_id
     WHERE fine_id = p_fine_id;
END$$

-- ---------------------------------------------------------------------
-- sp_monthly_borrow_summary: borrowing statistics per month of a year
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_monthly_borrow_summary(
    IN p_year SMALLINT UNSIGNED
)
BEGIN
    SELECT
        MONTH(l.borrowed_at)                        AS month_no,
        MONTHNAME(MIN(l.borrowed_at))               AS month_name,
        COUNT(*)                                    AS total_borrowed,
        SUM(l.returned_at IS NOT NULL)              AS total_returned,
        COUNT(DISTINCT l.member_id)                 AS unique_borrowers,
        COALESCE(SUM(f.amount), 0)                  AS fines_assessed
    FROM loans l
    LEFT JOIN fines f ON f.loan_id = l.loan_id
    WHERE YEAR(l.borrowed_at) = p_year
    GROUP BY MONTH(l.borrowed_at)
    ORDER BY month_no;
END$$

DELIMITER ;


-- =====================================================================
--  SECTION 5: SAMPLE DATA
-- =====================================================================

INSERT INTO library_settings (setting_key, setting_value, description) VALUES
('loan_days',        '7',    'Number of days a book can be borrowed'),
('max_active_loans', '3',    'Maximum books a member can borrow at once'),
('fine_per_day',     '5.00', 'Overdue fine per day in PHP');

-- Passwords: admin123 (librarians), member123 (members)
INSERT INTO users (user_id, username, password_hash, role, first_name, last_name, email, is_active) VALUES
(1, 'admin',          'pbkdf2:sha256:600000$fb3daa85abfb14b6$6a0bd6516054e9bb0f84b568242b84fd76b91a27ef03e585f1418ec390fa9faa', 'librarian', 'Library',  'Admin',     'admin@library.local',          1),
(2, 'jdelacruz',      'pbkdf2:sha256:600000$fb3daa85abfb14b6$6a0bd6516054e9bb0f84b568242b84fd76b91a27ef03e585f1418ec390fa9faa', 'librarian', 'Juan',     'Dela Cruz', 'juan.delacruz@library.local',  1),
(3, 'ana.reyes',      'pbkdf2:sha256:600000$97358e147931b052$65d7e6e7a6d487f05d6efc8b6c655d39a3b698072b090358f369adb894bc515b', 'member',    'Ana',      'Reyes',     'ana.reyes@student.local',      1),
(4, 'mark.garcia',    'pbkdf2:sha256:600000$97358e147931b052$65d7e6e7a6d487f05d6efc8b6c655d39a3b698072b090358f369adb894bc515b', 'member',    'Mark',     'Garcia',    'mark.garcia@student.local',    1),
(5, 'liza.mendoza',   'pbkdf2:sha256:600000$97358e147931b052$65d7e6e7a6d487f05d6efc8b6c655d39a3b698072b090358f369adb894bc515b', 'member',    'Liza',     'Mendoza',   'liza.mendoza@student.local',   1),
(6, 'paolo.bautista', 'pbkdf2:sha256:600000$97358e147931b052$65d7e6e7a6d487f05d6efc8b6c655d39a3b698072b090358f369adb894bc515b', 'member',    'Paolo',    'Bautista',  'paolo.bautista@student.local', 1),
(7, 'carla.torres',   'pbkdf2:sha256:600000$97358e147931b052$65d7e6e7a6d487f05d6efc8b6c655d39a3b698072b090358f369adb894bc515b', 'member',    'Carla',    'Torres',    'carla.torres@student.local',   1),
(8, 'kevin.ramos',    'pbkdf2:sha256:600000$97358e147931b052$65d7e6e7a6d487f05d6efc8b6c655d39a3b698072b090358f369adb894bc515b', 'member',    'Kevin',    'Ramos',     'kevin.ramos@student.local',    0);

INSERT INTO courses (course_id, course_code, course_name) VALUES
(1, 'BSIT', 'Bachelor of Science in Information Technology'),
(2, 'BSCS', 'Bachelor of Science in Computer Science'),
(3, 'BSIS', 'Bachelor of Science in Information Systems'),
(4, 'BSEMC', 'Bachelor of Science in Entertainment and Multimedia Computing');

INSERT INTO members (member_id, user_id, student_no, course_id, year_level, contact_no) VALUES
(1, 3, '2023-00101', 1, 3, '09171234501'),
(2, 4, '2023-00102', 2, 3, '09171234502'),
(3, 5, '2024-00103', 1, 2, '09171234503'),
(4, 6, '2022-00104', 3, 4, '09171234504'),
(5, 7, '2025-00105', 1, 1, '09171234505'),
(6, 8, '2022-00106', 2, 4, '09171234506');

INSERT INTO categories (category_id, name, description) VALUES
(1, 'Programming',      'Software development and programming languages'),
(2, 'Database Systems', 'Database design, SQL, and data management'),
(3, 'Networking',       'Computer networks and communications'),
(4, 'Web Development',  'HTML, CSS, JavaScript, and web technologies'),
(5, 'Mathematics',      'Discrete math, statistics, and related topics'),
(6, 'Fiction',          'Novels and literary works');

INSERT INTO authors (author_id, first_name, last_name) VALUES
(1,  'Robert C.',   'Martin'),
(2,  'Andrew',      'Hunt'),
(3,  'David',       'Thomas'),
(4,  'Ramez',       'Elmasri'),
(5,  'Shamkant B.', 'Navathe'),
(6,  'Abraham',     'Silberschatz'),
(7,  'Henry F.',    'Korth'),
(8,  'S.',          'Sudarshan'),
(9,  'Andrew S.',   'Tanenbaum'),
(10, 'Jon',         'Duckett'),
(11, 'Marijn',      'Haverbeke'),
(12, 'Eric',        'Matthes'),
(13, 'Kenneth H.',  'Rosen'),
(14, 'George',      'Orwell'),
(15, 'Harper',      'Lee'),
(16, 'Thomas H.',   'Cormen');

INSERT INTO books (book_id, isbn, title, category_id, publisher, publication_year, description) VALUES
(1,  '9780132350884', 'Clean Code',                               1, 'Prentice Hall',   2008, 'A handbook of agile software craftsmanship.'),
(2,  '9780135957059', 'The Pragmatic Programmer',                 1, 'Addison-Wesley',  2019, 'Your journey to mastery, 20th anniversary edition.'),
(3,  '9780133970777', 'Fundamentals of Database Systems',         2, 'Pearson',         2015, 'Comprehensive introduction to database concepts.'),
(4,  '9780078022159', 'Database System Concepts',                 2, 'McGraw-Hill',     2019, 'Classic textbook on database systems.'),
(5,  '9780132126953', 'Computer Networks',                        3, 'Pearson',         2010, 'Top-down look at how networks work.'),
(6,  '9781118008188', 'HTML and CSS: Design and Build Websites',  4, 'Wiley',           2011, 'A visual guide to HTML and CSS.'),
(7,  '9781593279509', 'Eloquent JavaScript',                      4, 'No Starch Press', 2018, 'A modern introduction to programming with JavaScript.'),
(8,  '9781718502703', 'Python Crash Course',                      1, 'No Starch Press', 2023, 'A hands-on, project-based introduction to Python.'),
(9,  '9781259676512', 'Discrete Mathematics and Its Applications',5, 'McGraw-Hill',     2018, 'Standard text for discrete mathematics.'),
(10, '9780451524935', '1984',                                     6, 'Signet Classics', 1961, 'A dystopian novel about surveillance and control.'),
(11, '9780061120084', 'To Kill a Mockingbird',                    6, 'Harper Perennial',2006, 'A novel about justice and growing up.'),
(12, '9780262046305', 'Introduction to Algorithms',               1, 'MIT Press',       2022, 'Comprehensive guide to algorithms.');

INSERT INTO book_authors (book_id, author_id) VALUES
(1, 1), (2, 2), (2, 3), (3, 4), (3, 5), (4, 6), (4, 7), (4, 8),
(5, 9), (6, 10), (7, 11), (8, 12), (9, 13), (10, 14), (11, 15), (12, 16);

INSERT INTO book_copies (copy_id, book_id, accession_no, status, acquired_date) VALUES
(1,  1,  'ACC-0001', 'available', '2024-06-01'),
(2,  1,  'ACC-0002', 'available', '2024-06-01'),
(3,  1,  'ACC-0003', 'available', '2025-01-15'),
(4,  2,  'ACC-0004', 'available', '2024-06-01'),
(5,  2,  'ACC-0005', 'available', '2024-06-01'),
(6,  3,  'ACC-0006', 'available', '2024-06-01'),
(7,  3,  'ACC-0007', 'available', '2024-06-01'),
(8,  3,  'ACC-0008', 'available', '2025-01-15'),
(9,  4,  'ACC-0009', 'available', '2024-06-01'),
(10, 4,  'ACC-0010', 'available', '2024-06-01'),
(11, 5,  'ACC-0011', 'available', '2024-06-01'),
(12, 5,  'ACC-0012', 'available', '2024-06-01'),
(13, 6,  'ACC-0013', 'available', '2024-08-20'),
(14, 6,  'ACC-0014', 'available', '2024-08-20'),
(15, 7,  'ACC-0015', 'available', '2024-08-20'),
(16, 7,  'ACC-0016', 'available', '2024-08-20'),
(17, 8,  'ACC-0017', 'available', '2025-01-15'),
(18, 8,  'ACC-0018', 'available', '2025-01-15'),
(19, 8,  'ACC-0019', 'available', '2025-01-15'),
(20, 9,  'ACC-0020', 'available', '2024-06-01'),
(21, 9,  'ACC-0021', 'available', '2024-06-01'),
(22, 10, 'ACC-0022', 'available', '2024-06-01'),
(23, 10, 'ACC-0023', 'available', '2024-06-01'),
(24, 11, 'ACC-0024', 'available', '2024-06-01'),
(25, 11, 'ACC-0025', 'lost',      '2024-06-01'),
(26, 12, 'ACC-0026', 'damaged',   '2025-01-15'),
(27, 12, 'ACC-0027', 'available', '2025-01-15');

-- Loans use dates RELATIVE to today, so the sample data always shows
-- a realistic mix of returned, active, and overdue loans whenever imported.

-- Historical (already returned) loans
INSERT INTO loans (loan_id, copy_id, member_id, issued_by, borrowed_at, due_date, returned_at, received_by) VALUES
(1, 1,  1, 1, NOW() - INTERVAL 40 DAY, CURDATE() - INTERVAL 33 DAY, NOW() - INTERVAL 34 DAY, 1),  -- on time
(2, 6,  2, 1, NOW() - INTERVAL 35 DAY, CURDATE() - INTERVAL 28 DAY, NOW() - INTERVAL 25 DAY, 2),  -- 3 days late
(3, 15, 3, 2, NOW() - INTERVAL 30 DAY, CURDATE() - INTERVAL 23 DAY, NOW() - INTERVAL 20 DAY, 1),  -- 3 days late
(4, 9,  4, 1, NOW() - INTERVAL 25 DAY, CURDATE() - INTERVAL 18 DAY, NOW() - INTERVAL 18 DAY, 1),  -- on time
(5, 1,  2, 2, NOW() - INTERVAL 20 DAY, CURDATE() - INTERVAL 13 DAY, NOW() - INTERVAL 14 DAY, 2),  -- on time
(6, 22, 1, 1, NOW() - INTERVAL 18 DAY, CURDATE() - INTERVAL 11 DAY, NOW() - INTERVAL 12 DAY, 1),  -- on time
(7, 2,  4, 1, NOW() - INTERVAL 15 DAY, CURDATE() - INTERVAL 8 DAY,  NOW() - INTERVAL 10 DAY, 2),  -- on time
(8, 17, 5, 2, NOW() - INTERVAL 14 DAY, CURDATE() - INTERVAL 7 DAY,  NOW() - INTERVAL 2 DAY,  1),  -- 5 days late
(9, 13, 6, 1, NOW() - INTERVAL 60 DAY, CURDATE() - INTERVAL 53 DAY, NOW() - INTERVAL 53 DAY, 1);  -- on time (Kevin, now deactivated)

-- Active loans (these pass through trg_loans_before_insert validation)
INSERT INTO loans (loan_id, copy_id, member_id, issued_by, borrowed_at, due_date) VALUES
(10, 3,  1, 1, NOW() - INTERVAL 3 DAY,  CURDATE() + INTERVAL 4 DAY),   -- Ana
(11, 11, 1, 1, NOW() - INTERVAL 2 DAY,  CURDATE() + INTERVAL 5 DAY),   -- Ana
(12, 10, 4, 2, NOW() - INTERVAL 1 DAY,  CURDATE() + INTERVAL 6 DAY),   -- Paolo
(13, 18, 5, 1, NOW() - INTERVAL 5 DAY,  CURDATE() + INTERVAL 2 DAY),   -- Carla
(14, 4,  2, 2, NOW() - INTERVAL 12 DAY, CURDATE() - INTERVAL 5 DAY);   -- Mark: OVERDUE by 5 days

-- Fines for late returns (amount is auto-computed)
INSERT INTO fines (fine_id, loan_id, days_overdue, rate_per_day, is_paid, paid_at, received_by) VALUES
(1, 2, 3, 5.00, 1, NOW() - INTERVAL 25 DAY, 2),   -- Mark: paid
(2, 3, 3, 5.00, 0, NULL, NULL),                   -- Liza: UNPAID (blocks borrowing)
(3, 8, 5, 5.00, 1, NOW() - INTERVAL 2 DAY,  1);   -- Carla: paid

-- =====================================================================
--  END OF SCRIPT
-- =====================================================================
