from config import DB_CONFIG
import mysql.connector
from decimal import Decimal, InvalidOperation

MIN_BALANCE = Decimal("1000")

# ---------------- Database Connection ----------------
try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    print("✓ Connected to bank database (bank_db) successfully\n")
except mysql.connector.Error as e:
    print(f"Error connecting to database: {e}")
    exit()


# ---------------- Create New Account ----------------
def create_account():
    try:
        name = input("Enter full name: ")
        email = input("Enter email: ")
        phone = input("Enter phone number: ")
        address = input("Enter address: ")
        account_type = input("Account type (savings/current): ").lower()

        if account_type not in ('savings', 'current'):
            print("Invalid account type.")
            return

        opening_balance = Decimal(input("Opening balance: "))
        if opening_balance < MIN_BALANCE:
            print(f"Minimum opening balance is {MIN_BALANCE}.")
            return

        cursor.execute(
            "INSERT INTO customers (full_name, email, phone, address) "
            "VALUES (%s, %s, %s, %s)",
            (name, email, phone, address)
        )
        customer_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO accounts (customer_id, account_type, balance, status) "
            "VALUES (%s, %s, %s, 'active')",
            (customer_id, account_type, opening_balance)
        )

        cursor.execute("SELECT LAST_INSERT_ID()")
        account_no = cursor.fetchone()[0]

        conn.commit()
        print("\nAccount created successfully.")
        print(f"Customer ID : {customer_id}")
        print(f"Account No  : {account_no}")

    except (InvalidOperation, ValueError):
        conn.rollback()
        print("Invalid input.")
    except Exception as e:
        conn.rollback()
        print("Failed to create account:", e)


# ---------------- Deposit ----------------
def deposit():
    try:
        acc_no = int(input("Enter account number: "))
        amt = Decimal(input("Enter deposit amount: "))

        if amt <= 0:
            print("Amount must be greater than zero.")
            return

        cursor.execute(
            "SELECT status FROM accounts WHERE account_no = %s FOR UPDATE",
            (acc_no,)
        )
        acc = cursor.fetchone()

        if acc is None or acc[0] != 'active':
            print("Account not found or inactive.")
            return

        cursor.execute(
            "INSERT INTO transactions (account_no, transaction_type, amount) "
            "VALUES (%s, 'deposit', %s)",
            (acc_no, amt)
        )

        cursor.execute(
            "UPDATE accounts SET balance = balance + %s WHERE account_no = %s",
            (amt, acc_no)
        )

        conn.commit()
        print("Deposit successful.")

    except Exception as e:
        conn.rollback()
        print("Transaction failed:", e)


# ---------------- Withdrawal ----------------
def withdrawal():
    try:
        acc_no = int(input("Enter account number: "))
        amt = Decimal(input("Enter withdrawal amount: "))

        if amt <= 0:
            print("Invalid amount.")
            return

        cursor.execute(
            "SELECT balance, status FROM accounts WHERE account_no = %s FOR UPDATE",
            (acc_no,)
        )
        bal = cursor.fetchone()

        if bal is None or bal[1] != 'active':
            print("Account not found or inactive.")
            return

        if bal[0] < amt or bal[0] - amt < MIN_BALANCE:
            print(f"Insufficient balance. Minimum balance of {MIN_BALANCE} must be maintained.")
            return

        cursor.execute(
            "INSERT INTO transactions (account_no, transaction_type, amount) "
            "VALUES (%s, 'withdrawal', %s)",
            (acc_no, amt)
        )

        cursor.execute(
            "UPDATE accounts SET balance = balance - %s WHERE account_no = %s",
            (amt, acc_no)
        )

        conn.commit()
        print("Withdrawal successful.")

    except Exception as e:
        conn.rollback()
        print("Transaction failed:", e)


# ---------------- Fund Transfer ----------------
def fund_transfer():
    try:
        from_acc = int(input("From account number: "))
        to_acc = int(input("To account number: "))
        amt = Decimal(input("Transfer amount: "))

        if amt <= 0 or from_acc == to_acc:
            print("Invalid transfer details.")
            return

        cursor.execute(
            "SELECT balance, status FROM accounts WHERE account_no = %s FOR UPDATE",
            (from_acc,)
        )
        from_bal = cursor.fetchone()

        cursor.execute(
            "SELECT balance, status FROM accounts WHERE account_no = %s FOR UPDATE",
            (to_acc,)
        )
        to_bal = cursor.fetchone()

        if (from_bal is None or to_bal is None or
                from_bal[1] != 'active' or to_bal[1] != 'active'):
            print("One or both accounts not found or inactive.")
            return

        if from_bal[0] < amt or from_bal[0] - amt < MIN_BALANCE:
            print(f"Insufficient balance. Minimum balance of {MIN_BALANCE} must be maintained.")
            return

        cursor.execute(
            "UPDATE accounts SET balance = balance - %s WHERE account_no = %s",
            (amt, from_acc)
        )

        cursor.execute(
            "UPDATE accounts SET balance = balance + %s WHERE account_no = %s",
            (amt, to_acc)
        )

        cursor.execute(
            "INSERT INTO transactions (account_no, transaction_type, amount) "
            "VALUES (%s, 'transfer', %s)",
            (from_acc, amt)
        )

        cursor.execute(
            "INSERT INTO transactions (account_no, transaction_type, amount) "
            "VALUES (%s, 'transfer', %s)",
            (to_acc, amt)
        )

        conn.commit()
        print("Fund transfer successful.")

    except Exception as e:
        conn.rollback()
        print("Transfer failed:", e)


# ---------------- Transaction History ----------------
def transaction_history():
    acc_no = int(input("Enter account number: "))

    cursor.execute(
        "SELECT transaction_type, amount, transaction_date "
        "FROM transactions WHERE account_no = %s "
        "ORDER BY transaction_date DESC",
        (acc_no,)
    )

    records = cursor.fetchall()

    if not records:
        print("No transactions found.")
        return

    print("\nType\t\tAmount\t\tDate")
    print("-" * 45)
    for t_type, amt, date in records:
        print(f"{t_type}\t{amt}\t{date}")


# ---------------- Search Menu ----------------
def search_menu():
    while True:
        print("\n----- Search Menu -----")
        print("1. Account Number")
        print("2. Customer Name")
        print("3. Phone Number")
        print("4. Email")
        print("5. Back")

        try:
            choice = int(input("Enter choice: "))
        except ValueError:
            print("Invalid input.")
            continue

        if choice == 5:
            break

        if choice == 1:
            value = input("Enter account number: ")
            cursor.execute("""
                SELECT a.account_no, c.full_name, c.phone, c.email,
                       a.account_type, a.balance, a.status
                FROM accounts a
                JOIN customers c ON a.customer_id = c.customer_id
                WHERE a.account_no = %s
            """, (value,))

        elif choice == 2:
            value = f"%{input('Enter name: ')}%"
            cursor.execute("""
                SELECT a.account_no, c.full_name, c.phone, c.email,
                       a.account_type, a.balance, a.status
                FROM accounts a
                JOIN customers c ON a.customer_id = c.customer_id
                WHERE c.full_name LIKE %s
            """, (value,))

        elif choice == 3:
            value = input("Enter phone number: ")
            cursor.execute("""
                SELECT a.account_no, c.full_name, c.phone, c.email,
                       a.account_type, a.balance, a.status
                FROM accounts a
                JOIN customers c ON a.customer_id = c.customer_id
                WHERE c.phone = %s
            """, (value,))

        elif choice == 4:
            value = input("Enter email: ")
            cursor.execute("""
                SELECT a.account_no, c.full_name, c.phone, c.email,
                       a.account_type, a.balance, a.status
                FROM accounts a
                JOIN customers c ON a.customer_id = c.customer_id
                WHERE c.email = %s
            """, (value,))
        else:
            print("Invalid choice.")
            continue

        rows = cursor.fetchall()

        if not rows:
            print("No records found.")
            continue

        print("\nAccount | Name | Phone | Email | Type | Balance | Status")
        print("-" * 95)
        for r in rows:
            print(*r, sep=" | ")


# ---------------- Main Menu ----------------
while True:
    print("\n----- Banking Menu -----")
    print("1. Create New Account")
    print("2. Deposit")
    print("3. Withdrawal")
    print("4. Fund Transfer")
    print("5. Transaction History")
    print("6. Search Account")
    print("7. Exit")

    try:
        choice = int(input("Enter choice: "))
    except ValueError:
        print("Invalid input.")
        continue

    match choice:
        case 1:
            create_account()
        case 2:
            deposit()
        case 3:
            withdrawal()
        case 4:
            fund_transfer()
        case 5:
            transaction_history()
        case 6:
            search_menu()
        case 7:
            cursor.close()
            conn.close()
            print("Database connection closed.")
            break
        case _:
            print("Invalid choice.")
