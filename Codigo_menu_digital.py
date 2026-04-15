from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import pandas as pd
import os
import json
from datetime import datetime
import pytz
from sqlalchemy import create_engine, text

# ==============================
# HORA COLOMBIA
# ==============================
def hora_colombia():
    zona = pytz.timezone("America/Bogota")
    return datetime.now(zona)

app = Flask(__name__)
app.secret_key = "supersecretkey"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "BASEDEDATOSMENUCOMIDASRAPIDAS.csv")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///" + os.path.join(BASE_DIR, "local.db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==============================
# TABLAS
# ==============================
def crear_tablas():
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero INTEGER,
            fecha TEXT,
            nombre TEXT,
            tipo_entrega TEXT,
            direccion TEXT,
            mesa TEXT,
            efectivo REAL,
            nequi REAL,
            total REAL
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS detalle_pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER,
            referencia TEXT,
            precio REAL
        );
        """))

crear_tablas()

# ==============================
# NUMERO PEDIDO
# ==============================
def generar_numero_pedido():
    archivo = os.path.join(BASE_DIR, "contador_pedidos.json")
    hoy = datetime.now().strftime("%Y-%m-%d")

    if not os.path.exists(archivo):
        data = {"fecha": hoy, "contador": 1}
    else:
        with open(archivo, "r") as f:
            data = json.load(f)

        if data["fecha"] != hoy:
            data["contador"] = 1
            data["fecha"] = hoy
        else:
            data["contador"] += 1

    with open(archivo, "w") as f:
        json.dump(data, f)

    return data["contador"]

# ==============================
# MENU
# ==============================
def cargar_menu():
    if not os.path.exists(CSV_PATH):
        return pd.DataFrame()

    df = pd.read_csv(CSV_PATH, sep=";")
    df.columns = df.columns.str.strip().str.upper().str.replace(" ", "")
    df["PRECIO"] = pd.to_numeric(df["PRECIO"], errors="coerce").fillna(0)
    return df

@app.context_processor
def carrito_global():
    carrito = session.get("carrito", [])
    total = sum(item["PRECIO"] for item in carrito)
    return dict(carrito_cantidad=len(carrito), carrito_total=total)

# ==============================
# RUTAS
# ==============================
@app.route("/")
def index():
    menu = cargar_menu()
    categorias = sorted(menu["CATEGORIA"].dropna().unique())
    return render_template("categorias.html", categorias=categorias)

@app.route("/categoria/<nombre>")
def ver_categoria(nombre):
    menu = cargar_menu()
    productos = menu[menu["CATEGORIA"] == nombre]
    return render_template("productos.html", categoria=nombre, productos=productos.to_dict(orient="records"))

@app.route("/agregar", methods=["POST"])
def agregar():
    session.setdefault("carrito", [])
    carrito = session["carrito"]

    cantidad = int(request.form.get("cantidad") or 1)

    for _ in range(cantidad):
        carrito.append({
            "REFERENCIA": request.form.get("referencia"),
            "DESCRIPCION": request.form.get("descripcion"),
            "PRECIO": float(request.form.get("precio")),
            "SALSAS": ", ".join(request.form.getlist("salsas")),
            "EXTRAS": ", ".join(request.form.getlist("extras"))
        })

    session["carrito"] = carrito
    session.modified = True

    return redirect(url_for("ver_carrito"))

@app.route("/carrito")
def ver_carrito():
    carrito = session.get("carrito", [])
    total = sum(item["PRECIO"] for item in carrito)
    return render_template("carrito.html", carrito=carrito, total=total)

# ==============================
# FINALIZAR
# ==============================
@app.route("/finalizar", methods=["POST"])
def finalizar():

    carrito = session.get("carrito", [])
    total = sum(item["PRECIO"] for item in carrito)

    pago_efectivo = float(request.form.get("pago_efectivo") or 0)
    pago_nequi = float(request.form.get("pago_nequi") or 0)

    pedido = {
        "numero": generar_numero_pedido(),
        "fecha": hora_colombia().strftime("%Y-%m-%d %H:%M:%S"),
        "nombre": request.form.get("nombre"),
        "tipo_entrega": request.form.get("tipo_entrega"),
        "direccion": request.form.get("direccion"),
        "mesa": request.form.get("mesa"),
        "efectivo": pago_efectivo,
        "nequi": pago_nequi
    }

    with engine.begin() as conn:

        conn.execute(text("""
            INSERT INTO pedidos (numero, fecha, nombre, tipo_entrega, direccion, mesa, efectivo, nequi, total)
            VALUES (:numero, :fecha, :nombre, :tipo_entrega, :direccion, :mesa, :efectivo, :nequi, :total)
        """), {**pedido, "total": total})

        pedido_id = result.fetchone()[0]

        for item in carrito:
            conn.execute(text("""
                INSERT INTO detalle_pedidos (pedido_id, referencia, precio)
                VALUES (:pedido_id, :referencia, :precio)
            """), {
                "pedido_id": pedido_id,
                "referencia": item["REFERENCIA"],
                "precio": item["PRECIO"]
            })

    session["pedido"] = pedido

    return render_template("confirmacion.html", pedido=pedido, carrito=carrito, total=total)

# ==============================
# TICKET HTML
# ==============================
# ==============================
# TICKET HTML
# ==============================
@app.route("/ticket")
def ticket():
    carrito = session.get("carrito", [])
    pedido = session.get("pedido", {})
    total = sum(item["PRECIO"] for item in carrito)
    return render_template("ticket.html", carrito=carrito, total=total, pedido=pedido)


# ==============================
# REPORTE (TEMPORAL)
# ==============================
@app.route("/reporte")
def reporte():
    return "Reporte funcionando (temporal)"


# ==============================
# TICKET PARA RAWBT
# ==============================
@app.route("/ticket_texto")
def ticket_texto():

    carrito = session.get("carrito", [])
    pedido = session.get("pedido", {})

    texto = "HAMBURMIL DECEPAZ\n"
    texto += f"{pedido.get('fecha')}\n"
    texto += f"Pedido #{pedido.get('numero')}\n"
    texto += "---------------------\n"

    for item in carrito:
        texto += f"{item['REFERENCIA']} ${int(item['PRECIO'])}\n"

    texto += "---------------------\n"
    texto += "Gracias por su compra\n"

    return texto, 200, {'Content-Type': 'text/plain'}


# ==============================
if __name__ == "__main__":
    app.run(debug=True)