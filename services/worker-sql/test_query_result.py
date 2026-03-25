import asyncio
import os
import sys

from app.modules.sql.tools.run_sql_query import _run_sql_query_internal

async def main():
    conn_str = "sqlite:///c:/Users/Lenovo/Downloads/finalproject/services/worker-sql/app/modules/sql/Chinook_Sqlite.sqlite"
    sql = """SELECT * FROM (SELECT 'Genre' AS Category, g.Name AS Name, SUM(il.UnitPrice * il.Quantity) AS TotalValue FROM Genre g JOIN Track t ON g.GenreId = t.GenreId JOIN InvoiceLine il ON t.TrackId = il.TrackId GROUP BY g.GenreId ORDER BY TotalValue DESC LIMIT 5) UNION ALL SELECT * FROM (SELECT 'Customer' AS Category, c.FirstName || ' ' || c.LastName AS Name, SUM(i.Total) AS TotalValue FROM Customer c JOIN Invoice i ON c.CustomerId = i.CustomerId GROUP BY c.CustomerId ORDER BY TotalValue DESC LIMIT 1);"""
    
    try:
        res = await _run_sql_query_internal(conn_str, sql)
        print("SUCCESS!")
        print(f"Row count: {res['row_count']}")
        print(f"Data: {res['data']}")
    except Exception as e:
        print("ERROR RUNNING QUERY:")
        print(e)
        
if __name__ == "__main__":
    asyncio.run(main())
