import mysql.connector

def connect_to_database():
    try:
        connection = mysql.connector.connect(
            host="localhost",  
            user="root",  
            password="alankrit_321#",  
            database="inv_management"
        )
        if connection.is_connected():
            print("Connected to MySQL Database")
        return connection
    except mysql.connector.Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None