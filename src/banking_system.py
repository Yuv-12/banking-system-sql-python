from config import DB_CONFIG
import mysql.connector
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MIN_BALANCE = Decimal("1000.00")


# ---------------- Helpers ----------------

def parse_money(prompt):
    try:
        val = Decimal(input(prompt).strip())
        if val <= 0:
            raise InvalidOperation
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        print("Invalid monetary amount.")
        return None


def valid_email(e):
    return "@" in e and "." in e


def valid_phone(p):
    return p.isdigit() and len(p) == 10


# ---------------- Database Connection ----------------

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    conn.autocommit = False
    cursor = conn.cursor()
    print("✓ Connected to bank database successfully\n")
except mysql.connector.Error as e:
    print("Database connection error:", e)
    exit()


# ---------------- Create Account ----------------

def create_account():
    try:
        name = input("Full name: ").strip()
        email = input("Email: ").strip()
        phone = input("Phone: ").strip()
        address = input("Address: ").strip()
        acc_type = input("Account type (savings/current): ").lower().strip()

        if not name:
            print("Name required.")
            return
        if not valid_email(email):
            print("Invalid email.")
            return
        if not valid_phone(phone):
            print("Invalid phone number.")
            return
        if acc_type not in ("savings", "current"):
            print("Invalid account type.")
            return

        opening = parse_money("Opening balance: ")
        if opening is None:
            return
        if opening < MIN_BALANCE:
            print(f"Minimum opening balance is {MIN_BALANCE}.")
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
        print("\n✓ Account created")
        print("Customer ID:", cust_id)
        print("Account No :", acc_no)

    except Exception as e:
        conn.rollback()
        print("Account creation failed:", e)


# ---------------- Deposit ----------------

def deposit():
    try:
        acc_no = int(input("Account number: "))
        amt = parse_money("Deposit amount: ")
        if amt is None:
            return

        cursor.execute(
            "SELECT status FROM accounts WHERE account_no=%s FOR UPDATE",
            (acc_no,)
        )
        row = cursor.fetchone()
        if not row or row[0] != "active":
            print("Account not active/found.")
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
        acc_no = int(input("Account number: "))
        amt = parse_money("Withdrawal amount: ")
        if amt is None:
            return

        cursor.execute(
            "SELECT balance,status FROM accounts WHERE account_no=%s FOR UPDATE",
            (acc_no,)
        )
        row = cursor.fetchone()
        if not row or row[1] != "active":
            print("Account not active/found.")
            return

        bal = Decimal(row[0])

        if bal - amt < MIN_BALANCE:
            print(f"Minimum balance {MIN_BALANCE} must remain.")
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


# ---------------- Fund Transfer ----------------

def fund_transfer():
    try:
        from_acc = int(input("From account: "))
        to_acc = int(input("To account: "))
        if from_acc == to_acc:
            print("Cannot transfer to same account.")
            return

        amt = parse_money("Transfer amount: ")
        if amt is None:
            return

        # deadlock-safe lock order
        first, second = sorted([from_acc, to_acc])

        cursor.execute(
            "SELECT account_no,balance,status FROM accounts "
            "WHERE account_no IN (%s,%s) FOR UPDATE",
            (first, second)
        )
        rows = cursor.fetchall()
        if len(rows) != 2:
            print("One account not found.")
            return

        data = {r[0]: (Decimal(r[1]), r[2]) for r in rows}

        if data[from_acc][1] != "active" or data[to_acc][1] != "active":
            print("One account inactive.")
            return

        if data[from_acc][0] - amt < MIN_BALANCE:
            print("Minimum balance rule violated.")
            return

        cursor.execute(
            "UPDATE accounts SET balance = balance - %s WHERE account_no=%s",
            (amt, from_acc)
        )
        cursor.execute(
            "UPDATE accounts SET balance = balance + %s WHERE account_no=%s",
            (amt, to_acc)
        )

        cursor.execute(
            "INSERT INTO transactions(account_no,transaction_type,amount,from_account,to_account) "
            "VALUES (%s,'transfer',%s,%s,%s)",
            (from_acc, amt, from_acc, to_acc)
        )

        cursor.execute(
            "INSERT INTO transactions(account_no,transaction_type,amount,from_account,to_account) "
            "VALUES (%s,'transfer',%s,%s,%s)",
            (to_acc, amt, from_acc, to_acc)
        )

        conn.commit()
        print("✓ Transfer successful")

    except Exception as e:
        conn.rollback()
        print("Transfer failed:", e)


# ---------------- Transaction History ----------------

def transaction_history():
    try:
        acc_no = int(input("Account number: "))
        cursor.execute(
            "SELECT transaction_type,amount,transaction_date,from_account,to_account "
            "FROM transactions WHERE account_no=%s "
            "ORDER BY transaction_date DESC",
            (acc_no,)
        )
        rows = cursor.fetchall()

        if not rows:
            print("No transactions.")
            return

        print("\nType        Amount      Date                  From  To")
        print("-" * 60)

        for t, a, d, f, to in rows:
            print(f"{t:<12}{Decimal(a):>10.2f}   {str(d):<20} {f or '-':<5} {to or '-'}")

    except Exception as e:
        print("History fetch failed:", e)


# ---------------- Search ----------------

def search_menu():
    while True:
        print("\nSearch by:")
        print("1 Account No")
        print("2 Name")
        print("3 Phone")
        print("4 Email")
        print("5 Back")

        try:
            ch = int(input("Choice: "))
        except ValueError:
            continue

        if ch == 5:
            return

        field_map = {
            1: ("a.account_no=%s", input("Account No: ")),
            2: ("c.full_name LIKE %s", f"%{input('Name: ')}%"),
            3: ("c.phone=%s", input("Phone: ")),
            4: ("c.email=%s", input("Email: "))
        }

        if ch not in field_map:
            continue

        cond, val = field_map[ch]

        cursor.execute(f"""
            SELECT a.account_no,c.full_name,c.phone,c.email,
                   a.account_type,a.balance,a.status
            FROM accounts a
            JOIN customers c USING(customer_id)
            WHERE {cond}
        """, (val,))

        rows = cursor.fetchall()
        if not rows:
            print("No records.")
            continue

        for r in rows:
            print(
                r[0], r[1], r[2], r[3],
                r[4], f"{Decimal(r[5]):.2f}", r[6],
                sep=" | "
            )


# ---------------- Main Menu ----------------

while True:
    print("\n--- Banking Menu ---")
    print("1 Create Account")
    print("2 Deposit")
    print("3 Withdrawal")
    print("4 Transfer")
    print("5 History")
    print("6 Search")
    print("7 Exit")

    try:
        c = int(input("Choice: "))
    except ValueError:
        continue

    if c == 1:
        create_account()
    elif c == 2:
        deposit()
    elif c == 3:
        withdrawal()
    elif c == 4:
        fund_transfer()
    elif c == 5:
        transaction_history()
    elif c == 6:
        search_menu()
    elif c == 7:
        break

cursor.close()
conn.close()
print("✓ DB closed")
