import psycopg2 #PostgreSQL database adapter for Python
import json

conn = psycopg2.connect( #Later make a connection pool as FastAPI runs multiple workers, connection may crash
    dbname="scraper_db",
    user="mahanshgaur",
    host="localhost",
    port="5432"
)

def save_raw_product(product_data, url):
    
    cur = conn.cursor() #A cursor is an object used to run SQL commands.
                        #Think of it like a remote control for the database.

    cur.execute(
        """
        INSERT INTO raw_products (
            source_url,
            vendor,
            data
        )
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        #These are placeholders.
        #Why not write values directly?
        #Bad practice:
        #VALUES ('url', 'Quartz', '{...}')
        #Because of SQL injection risk.

        (
            #These values replace the %s placeholders.
            url,
            product_data["vendor"],
            json.dumps(product_data)
        )
    )

    product_id = cur.fetchone()[0] #Fetch one row from query result.
    conn.commit() #save permanently

    cur.close()

    return product_id

def save_ai_product(raw_product_id, ai_data):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ai_products (
            raw_product_id, 
            ai_data
        )
        VALUES (%s, %s)
        """,
        (
            raw_product_id,
            json.dumps(ai_data)
        )
    )
    conn.commit()
    cur.close()

def get_raw_product(product_id):
    cur = conn.cursor()
    cur.execute("SELECT data FROM raw_products WHERE id = %s", (product_id,))
    row = cur.fetchone()
    cur.close()
    return row[0] if row else None