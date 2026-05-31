import sqlite3
import pandas as pd
from datetime import datetime

def audit_crm(db_name="crm_test.db"):
    conn = sqlite3.connect(db_name)
    
    # Query critical projects
    query = "SELECT * FROM projects WHERE status = 'Critical'"
    df = pd.read_sql_query(query, conn)
    
    conn.close()
    
    if df.empty:
        return "No critical projects found."
    
    # Generate a report
    report = "# CRM Audit Report - Critical Projects\n\n"
    report += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for index, row in df.iterrows():
        report += f"## {row['name']}\n"
        report += f"- **Client:** {row['client']}\n"
        report += f"- **Budget:** ${row['budget']:,}\n"
        report += f"- **Deadline:** {row['deadline']}\n\n"
        
    return report

if __name__ == "__main__":
    # Ensure database exists
    import os
    if not os.path.exists("crm_test.db"):
        from create_db import create_sample_db
        create_sample_db()
        
    print(audit_crm())
