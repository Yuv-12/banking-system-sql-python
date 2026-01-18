# Banking System using Python & MySQL

## Overview
A console-based banking system built using Python and MySQL that supports
account creation, deposits, withdrawals, fund transfers, and transaction history.
The project demonstrates ACID-compliant transactions and secure database handling.

## Features
- Create customer and bank accounts
- Deposit and withdrawal with minimum balance enforcement
- Fund transfer between accounts
- Transaction history tracking
- Account search by multiple parameters
- MySQL row-level locking using FOR UPDATE

## Technologies Used
- Python 3
- MySQL
- mysql-connector-python

## Database Design
- Customers
- Accounts
- Transactions

## Setup Instructions

1. Clone the repository: git clone https://github.com/Yuv-12/banking-system-sql-python.git
   
2. Install dependencies: pip install -r requirements.txt
    
3. Setup database:
   - Open MySQL
   - Run `sql/schema.sql`

4. Configure database:
   - Copy `config/config.py.example` → `config/config.py`
   - Update credentials

5. Run the project: python src/banking_system.py


## Key Concepts Demonstrated
- SQL transactions and rollback
- Row-level locking (`FOR UPDATE`)
- Decimal handling for financial accuracy
- Input validation and error handling
- Secure parameterized queries

## Author
Yuvraj Gupta



