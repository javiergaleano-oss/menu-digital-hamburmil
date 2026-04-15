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

# ==============================
# APP
# ==============================
app = Flask(__name__)
app.secret_key = "supersecretkey"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "BASEDEDATOSMENUCOMIDASRAPIDAS.csv")

# ==============================
# BASE DE DATOS
# ==============================
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///" + os.path.join(BASE_DIR, "local.db")


engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==============================
# CREAR TABLAS (CORREGIDO)
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
# NUMERO DE PEDIDO
# ==============================
def generar_numero_pedido():
    archivo = os.path.join(BASE_DIR, "contador_pedidos.json")
    hoy = datetime.now().strftime("%Y-%m-%d")

    try:
        if not os.path.exists(archivo):
            data = {"fecha": hoy, "contador": 1}
        else:
            with open(archivo, "r") as f:
                data = json.load(f)

            if data.get("fecha") != hoy:
                data["contador"] = 1
                data["fecha"] = hoy
            else:
                data["contador"] += 1

        with open(archivo, "w") as f:
            json.dump(data, f)

        return data["contador"]

    except:
        return 1

# ==============================
# MENU
# ==============================
def cargar_menu():
    if not os.path.exists(CSV_PATH):
        return pd.DataFrame()

    df = pd.read_csv(CSV_PATH, encoding="utf-8", sep=";")
    df.columns = df.columns.str.strip().str.upper().str.replace(" ", "", regex=False)
    df["REFERENCIA"] = df["REFERENCIA"].astype(str)
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

# ==============================
# CARRITO
# ==============================
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
            "CATEGORIA": request.form.get("categoria"),
            "SALSAS": ", ".join(request.form.getlist("salsas")),
            "EXTRAS": ", ".join(request.form.getlist("extras"))
        })

    session["carrito"] = carrito
    session.modified = True

    return redirect(url_for("ver_carrito"))

@app.route("/eliminar/<int:index>")
def eliminar(index):
    carrito = session.get("carrito", [])
    if 0 <= index < len(carrito):
        carrito.pop(index)

    session["carrito"] = carrito
    session.modified = True

    return redirect(url_for("ver_carrito"))

@app.route("/duplicar/<int:index>")
def duplicar(index):
    carrito = session.get("carrito", [])
    if 0 <= index < len(carrito):
        carrito.append(carrito[index].copy())

    session["carrito"] = carrito
    session.modified = True

    return redirect(url_for("ver_carrito"))

# ==============================
# EDITAR
# ==============================
@app.route("/editar/<int:index>")
def editar(index):
    carrito = session.get("carrito", [])

    if not carrito or index >= len(carrito):
        flash("⚠️ Producto no disponible")
        return redirect(url_for("ver_carrito"))

    return render_template("editar_producto.html", item=carrito[index], index=index)

@app.route("/actualizar/<int:index>", methods=["POST"])
def actualizar(index):
    carrito = session.get("carrito", [])

    if not carrito or index >= len(carrito):
        return redirect(url_for("ver_carrito"))

    carrito[index]["SALSAS"] = ", ".join(request.form.getlist("salsas"))
    carrito[index]["EXTRAS"] = ", ".join(request.form.getlist("extras"))

    session["carrito"] = carrito
    session.modified = True

    return redirect(url_for("ver_carrito"))

# ==============================
# VER CARRITO
# ==============================
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

    total_pagado = pago_efectivo + pago_nequi

    restante = max(0, total - total_pagado)
    cambio = max(0, total_pagado - total)

    pedido = {
        "numero": generar_numero_pedido(),
        "fecha": hora_colombia().strftime("%Y-%m-%d %H:%M:%S"),
        "nombre": request.form.get("nombre"),
        "tipo_entrega": request.form.get("tipo_entrega"),
        "direccion": request.form.get("direccion"),
        "mesa": request.form.get("mesa"),
        "efectivo": pago_efectivo,
        "nequi": pago_nequi,
        "restante": restante,
        "cambio": cambio
    }

    with engine.begin() as conn:

        conn.execute(text("""
            INSERT INTO pedidos (numero, fecha, nombre, tipo_entrega, direccion, mesa, efectivo, nequi, total)
            VALUES (:numero, :fecha, :nombre, :tipo_entrega, :direccion, :mesa, :efectivo, :nequi, :total)
        """), {
            "numero": pedido["numero"],
            "fecha": pedido["fecha"],
            "nombre": pedido["nombre"],
            "tipo_entrega": pedido["tipo_entrega"],
            "direccion": pedido["direccion"],
            "mesa": pedido["mesa"],
            "efectivo": pedido["efectivo"],
            "nequi": pedido["nequi"],
            "total": total
        })

        pedido_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()

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
# REPORTE
# ==============================
@app.route("/reporte")
def reporte():
    from io import BytesIO

    resumen = pd.read_sql("""
        SELECT 
            DATE(fecha) as fecha,
            SUM(total) as venta_total,
            SUM(efectivo) as efectivo,
            SUM(nequi) as nequi
        FROM pedidos
        GROUP BY DATE(fecha)
        ORDER BY DATE(fecha) DESC
    """, engine)

    productos = pd.read_sql("""
        SELECT 
            DATE(p.fecha) as fecha,
            d.referencia,
            COUNT(d.referencia) as cantidad,
            SUM(d.precio) as total
        FROM detalle_pedidos d
        JOIN pedidos p ON d.pedido_id = p.id
        GROUP BY DATE(p.fecha), d.referencia
        ORDER BY DATE(p.fecha) DESC
    """, engine)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        resumen.to_excel(writer, index=False, sheet_name="Resumen")
        productos.to_excel(writer, index=False, sheet_name="Productos")

    output.seek(0)

    return send_file(output, download_name="reporte.xlsx", as_attachment=True)

# ==============================
# TICKET
# ==============================
@app.route("/ticket")
def ticket():
    carrito = session.get("carrito", [])
    pedido = session.get("pedido", {})
    total = sum(item["PRECIO"] for item in carrito)
    return render_template("ticket.html", carrito=carrito, total=total, pedido=pedido)

@app.route("/limpiar")
def limpiar():
    session.clear()
    return redirect(url_for("index"))

# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    app.run(debug=True)