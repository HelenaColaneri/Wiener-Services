import sqlite3
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "repuestos.db"

EXCEL_MASTER = DATA_DIR / "repuestos_master.xlsx"


def exportar_excel_master():
    """
    Sobrescribe SIEMPRE el Excel maestro.
    Nunca crea copias nuevas.
    """
    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql_query(
        "SELECT * FROM repuestos ORDER BY codigo_wiener",
        conn
    )

    conn.close()

    df.to_excel(EXCEL_MASTER, index=False)
    return EXCEL_MASTER
