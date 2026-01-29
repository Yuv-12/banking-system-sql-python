from config import DB_CONFIG
import mysql.connector
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import sys

MIN_BALANCE = Decimal("1000.00")


# ---------------- Helpers ----------------

def parse_money(prompt):
    try:
        val = Decimal(input(prompt).strip())
        if val <= 0:
            raise InvalidOperation
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        print("Invalid monetary amount.")
        return None


def parse_int(prompt):
    try:
        return int(input(prompt).strip())
    except ValueError:
        print("Invalid number.")
        return None


def valid_email(e):
    return "@" in e and "." in e and len(e) >= 5


def valid_phone(p):
    return p.isdigit() and len(p) == 10


# ---------------- DB Connect ----------------

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    conn.autocommit = False
    cursor = conn.cursor(dictionary=True)
    print("✓ Connected to bank database\n")
except mysql.connector.Error as e:
    print("DB connection error:", e)
    sys.exit()


# ---------------- Create Account ----------------

def create_account():
    try:
        name = input("Full name: ").strip()
        email = input("Email: ").strip().lower()
        phone = input("Phone: ").strip()
        address = input("Address: ").strip()
        acc_type = input("Type (savings/current): ").lower().strip()

        if not name:
            print("Name required."); return
        if not valid_email(email):
            print("Invalid email."); return
        if not valid_phone(phone):
            print("Invalid phone."); return
        if acc_type not in ("savings", "current"):
            print("Invalid account type."); return

        # prevent duplicates
        cursor.execute("SELECT 1 FROM customers WHERE email=%s OR phone=%s", (email, phone))
        if cursor.fetchone():
            print("Customer with email/phone already exists.")
            return

        opening = parse_money("Opening balance: ")
        if not opening:
            return
        if opening < MIN_BALANCE:
            print(f"Minimum opening balance is {MIN_BALANCE}")
            return

        cursor.execute(
            "INSERT INTO customers(full_name,email,phone,address) VALUES (%s,%s,%s,%s)",
            (name, email, phone, address)
        )
        cust_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO accounts(customer_id,account_type,balance,status) "
            "VALUES (%s,%s,%s,'active')",
            (cust_id, acc_type, opening)
        )
        acc_no = cursor.lastrowid

        cursor.execute(
            "INSERT INTO transactions(account_no,transaction_type,amount) "
            "VALUES (%s,'deposit',%s)",
            (acc_no, opening)
        )

        conn.commit()
        print(f"✓ Account created | Customer {cust_id} | Account {acc_no}")

    except Exception as e:
        conn.rollback()
        print("Create failed:", e)


# ---------------- Deposit ----------------

def deposit():
    try:
        acc_no = parse_int("Account number: ")
        if not acc_no: return

        amt = parse_money("Deposit amount: ")
        if not amt: return

        cursor.execute(
            "SELECT status FROM accounts WHERE account_no=%s FOR UPDATE",
            (acc_no,)
        )
        row = cursor.fetchone()
        if not row or row["status"] != "active":
            print("Account invalid/inactive.")
            conn.rollback()
            return

        cursor.execute(
            "UPDATE accounts SET balance = balance + %s WHERE account_no=%s",
            (amt, acc_no)
        )

        cursor.execute(
            "INSERT INTO transactions(account_no,transaction_type,amount) "
            "VALUES (%s,'deposit',%s)",
            (acc_no, amt)
        )

        conn.commit()
        print("✓ Deposit successful")

    except Exception as e:
        conn.rollback()
        print("Deposit failed:", e)


# ---------------- Withdrawal ----------------

def withdrawal():
    try:
        acc_no = parse_int("Account number: ")
        if not acc_no: return

        amt = parse_money("Withdrawal amount: ")
        if not amt: return

        cursor.execute(
            "SELECT balance,status FROM accounts WHERE account_no=%s FOR UPDATE",
            (acc_no,)
        )
        row = cursor.fetchone()
        if not row or row["status"] != "active":
            print("Account invalid/inactive.")
            conn.rollback()
            return

        bal = Decimal(row["balance"])
        if bal - amt < MIN_BALANCE:
            print("Minimum balance violation.")
            conn.rollback()
            return

        cursor.execute(
            "UPDATE accounts SET balance = balance - %s WHERE account_no=%s",
            (amt, acc_no)
        )

        cursor.execute(
            "INSERT INTO transactions(account_no,transaction_type,amount) "
            "VALUES (%s,'withdrawal',%s)",
            (acc_no, amt)
        )

        conn.commit()
        print("✓ Withdrawal successful")

    except Exception as e:
        conn.rollback()
        print("Withdrawal failed:", e)


# ---------------- Transfer ----------------

def fund_transfer():
    try:
        from_acc = parse_int("From account: ")
        to_acc = parse_int("To account: ")
        if not from_acc or not to_acc or from_acc == to_acc:
            print("Invalid accounts.")
            return

        amt = parse_money("Transfer amount: ")
        if not amt: return

        a, b = sorted([from_acc, to_acc])

        cursor.execute(
            "SELECT account_no,balance,status FROM accounts "
            "WHERE account_no IN (%s,%s) FOR UPDATE",
            (a, b)
        )
        rows = cursor.fetchall()
        if len(rows) != 2:
            print("Account missing.")
            conn.rollback()
            return

        data = {r["account_no"]: r for r in rows}

        if data[from_acc]["status"] != "active" or data[to_acc]["status"] != "active":
            print("Inactive account.")
            conn.rollback()
            return

        if Decimal(data[from_acc]["balance"]) - amt < MIN_BALANCE:
            print("Minimum balance violation.")
            conn.rollback()
            return

        cursor.execute("UPDATE accounts SET balance=balance-%s WHERE account_no=%s", (amt, from_acc))
        cursor.execute("UPDATE accounts SET balance=balance+%s WHERE account_no=%s", (amt, to_acc))

        for acc in (from_acc, to_acc):
            cursor.execute(
                "INSERT INTO transactions(account_no,transaction_type,amount,from_account,to_account) "
                "VALUES (%s,'transfer',%s,%s,%s)",
                (acc, amt, from_acc, to_acc)
            )

        conn.commit()
        print("✓ Transfer successful")

    except Exception as e:
        conn.rollback()
        print("Transfer failed:", e)


# ---------------- History ----------------

def transaction_history():
    acc_no = parse_int("Account number: ")
    if not acc_no: return

    cursor.execute("SELECT 1 FROM accounts WHERE account_no=%s", (acc_no,))
    if not cursor.fetchone():
        print("Account not found.")
        return

    cursor.execute("""
        SELECT transaction_type,amount,transaction_date,
               COALESCE(from_account,'-') fa,
               COALESCE(to_account,'-') ta
        FROM transactions
        WHERE account_no=%s
        ORDER BY transaction_date DESC
    """, (acc_no,))

    rows = cursor.fetchall()
    if not rows:
        print("No transactions."); return

    print("\nType        Amount      Date                  From  To")
    print("-"*60)
    for r in rows:
        print(f"{r['transaction_type']:<12}{Decimal(r['amount']):>10.2f}   "
              f"{str(r['transaction_date']):<20} {r['fa']:<5} {r['ta']}")


# ---------------- Search ----------------

def search_menu():
    while True:
        print("\n1 AccNo  2 Name  3 Phone  4 Email  5 Back")
        ch = parse_int("Choice: ")
        if ch == 5: return

        fields = {
            1: ("a.account_no=%s", input("AccNo: ")),
            2: ("c.full_name LIKE %s", f"%{input('Name: ')}%"),
            3: ("c.phone=%s", input("Phone: ")),
            4: ("c.email=%s", input("Email: ").lower())
        }
        if ch not in fields: continue

        cond, val = fields[ch]

        cursor.execute(f"""
            SELECT a.account_no,c.full_name,c.phone,c.email,
                   a.account_type,a.balance,a.status
            FROM accounts a
            JOIN customers c USING(customer_id)
            WHERE {cond}
        """, (val,))

        for r in cursor.fetchall():
            print(r["account_no"], r["full_name"], r["phone"],
                  r["email"], r["account_type"],
                  f"{Decimal(r['balance']):.2f}", r["status"], sep=" | ")


# ---------------- Main Loop ----------------

try:
    while True:
        print("\n1 Create 2 Deposit 3 Withdraw 4 Transfer 5 History 6 Search 7 Exit")
        c = parse_int("Choice: ")
        if c == 1: create_account()
        elif c == 2: deposit()
        elif c == 3: withdrawal()
        elif c == 4: fund_transfer()
        elif c == 5: transaction_history()
        elif c == 6: search_menu()
        elif c == 7: break

except KeyboardInterrupt:
    print("\nInterrupted by user.")

finally:
    cursor.close()
    conn.close()
    print("✓ DB closed")
