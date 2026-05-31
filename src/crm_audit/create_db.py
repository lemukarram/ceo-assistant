import sqlite3

def create_sample_db(db_name="crm_test.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Create Projects table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        client TEXT NOT NULL,
        status TEXT NOT NULL,
        budget REAL,
        deadline DATE
    )
    ''')

    # Insert sample data
    projects = [
        ('Project Alpha', 'TechCorp', 'In Progress', 50000, '2026-06-30'),
        ('Project Beta', 'HealthPlus', 'Completed', 75000, '2026-05-15'),
        ('Project Gamma', 'FinanceFlow', 'Critical', 120000, '2026-06-10'),
        ('Project Delta', 'EduTech', 'Pending', 30000, '2026-07-01'),
        ('Project Epsilon', 'RetailGurus', 'Critical', 95000, '2026-06-05')
    ]

    cursor.executemany('INSERT INTO projects (name, client, status, budget, deadline) VALUES (?, ?, ?, ?, ?)', projects)

    conn.commit()
    conn.close()
    print(f"Sample CRM database '{db_name}' created with {len(projects)} projects.")

if __name__ == "__main__":
    create_sample_db()
