import sqlite3
from contextlib import closing
from datetime import datetime
from typing import List, Tuple, Optional, Dict
from utils.logger import setup_logger

logger = setup_logger('database')

def init_db():
    logger.info("Initializing database...")
    with closing(sqlite3.connect("medical_chatbot.db")) as conn:
        c = conn.cursor()
        
        # Create medical_data table
        c.execute('''CREATE TABLE IF NOT EXISTS medical_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        data_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        analysis TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )''')
        
        # Create chat_history table with index on name and chat_type
        c.execute('''CREATE TABLE IF NOT EXISTS chat_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        chat_type TEXT NOT NULL,
                        user_input TEXT NOT NULL,
                        response TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )''')
        
        # Add indexes for better query performance
        c.execute('''CREATE INDEX IF NOT EXISTS idx_chat_history_name_type 
                    ON chat_history(name, chat_type)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_medical_data_name_type 
                    ON medical_data(name, data_type)''')
        
        conn.commit()
        logger.info("Database initialized successfully")

def save_medical_data(name: str, data_type: str, content: str, analysis: str) -> int:
    
    logger.info(f"Saving medical data for {name} of type {data_type}")
    try:
        # Add content validation
        if isinstance(content, bytes):
            content = content.decode('utf-8')
            
        with closing(sqlite3.connect("medical_chatbot.db")) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO medical_data 
                        (name, data_type, content, analysis)
                        VALUES (?, ?, ?, ?)''',
                    (name, data_type, str(content), str(analysis)))
            last_id = c.lastrowid
            conn.commit()
            logger.info(f"Medical data saved successfully with ID: {last_id}")
            return last_id
    except sqlite3.Error as e:
        logger.error(f"Error saving medical data: {e}")
        raise

def get_medical_data_by_id(id: int, data_type: Optional[str] = None) -> Tuple[Optional[List[Tuple]], Optional[str]]:
   
    logger.info(f"Retrieving medical data for ID: {id}" + (f" of type {data_type}" if data_type else ""))
    try:
        with closing(sqlite3.connect("medical_chatbot.db")) as conn:
            c = conn.cursor()
            # First get the patient name associated with this ID
            c.execute("SELECT DISTINCT name FROM medical_data WHERE id = ?", (id,))
            name_result = c.fetchone()
            
            if name_result:
                name = name_result[0]
                if data_type:
                    c.execute("""SELECT * FROM medical_data 
                               WHERE name = ? AND data_type = ? 
                               ORDER BY timestamp DESC""", (name, data_type))
                else:
                    c.execute("""SELECT * FROM medical_data 
                               WHERE name = ? 
                               ORDER BY timestamp DESC""", (name,))
                data = c.fetchall()
                return data, name
            return None, None
    except sqlite3.Error as e:
        logger.error(f"Error retrieving medical data: {e}")
        raise

def save_chat(name: str, chat_type: str, user_input: str, response: str) -> int:
    
    logger.info(f"Saving chat for {name} of type {chat_type}")
    try:
        with closing(sqlite3.connect("medical_chatbot.db")) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO chat_history (name, chat_type, user_input, response)
                        VALUES (?, ?, ?, ?)''',
                    (name, chat_type, user_input, response))
            last_id = c.lastrowid
            conn.commit()
            logger.info(f"Chat saved successfully with ID: {last_id}")
            return last_id
    except sqlite3.Error as e:
        logger.error(f"Error saving chat: {e}")
        raise

def get_chat_history(name: str, chat_type: str) -> List[Dict]:
    
    logger.info(f"Retrieving chat history for {name} of type {chat_type}")
    try:
        with closing(sqlite3.connect("medical_chatbot.db")) as conn:
            conn.row_factory = sqlite3.Row  # This enables dictionary access by column name
            c = conn.cursor()
            c.execute("""SELECT user_input as question, response, timestamp 
                        FROM chat_history 
                        WHERE name = ? AND chat_type = ? 
                        ORDER BY timestamp ASC""", (name, chat_type))
            
            # Convert Row objects to dictionaries
            chat_history = [dict(row) for row in c.fetchall()]
            logger.info(f"Retrieved {len(chat_history)} chat messages")
            return chat_history
    except sqlite3.Error as e:
        logger.error(f"Error retrieving chat history: {e}")
        raise

def clear_chat_history(name: str, chat_type: str) -> int:
  
    logger.info(f"Clearing chat history for {name} of type {chat_type}")
    try:
        with closing(sqlite3.connect("medical_chatbot.db")) as conn:
            c = conn.cursor()
            c.execute("""DELETE FROM chat_history 
                        WHERE name = ? AND chat_type = ?""", (name, chat_type))
            deleted_count = c.rowcount
            conn.commit()
            logger.info(f"Cleared {deleted_count} chat messages")
            return deleted_count
    except sqlite3.Error as e:
        logger.error(f"Error clearing chat history: {e}")
        raise